import { makeExtendSchemaPlugin, gql } from 'graphile-utils';

const DOMAIN_SERVER_URL = process.env.DOMAIN_SERVER_URL || 'http://app:8000';

interface SendChatInput {
  chatbotId: number;
  sessionId: string;
  message: string;
}

interface SupervisorResponse {
  response: string;
  tool_calls?: string[];
  sources?: string[];
}

export const ChatPlugin = makeExtendSchemaPlugin((build: any) => {
  const { pgSql: sql } = build;

  return {
    typeDefs: gql`
      input SendChatInput {
        chatbotId: Int!
        sessionId: String!
        message: String!
      }

      type ChatbotMessagePayload {
        messageId: Int!
        sessionId: String!
        role: String!
        content: String!
        toolCalls: [String]
        sources: [String]
        elapsedMs: Float
        createdAt: String
      }

      type SendChatPayload {
        userMessage: ChatbotMessagePayload!
        botMessage: ChatbotMessagePayload!
      }

      extend type Mutation {
        sendChat(input: SendChatInput!): SendChatPayload!
      }
    `,
    resolvers: {
      Mutation: {
        sendChat: async (
          _parent: unknown,
          args: { input: SendChatInput },
          context: { pgClient: any; req: any },
        ) => {
          const { chatbotId, sessionId, message } = args.input;
          const { pgClient } = context;
          const userId = context.req?.userId;

          if (!userId) {
            throw new Error('Authentication required');
          }

          // 1. Load chatbot settings from DB
          const chatbotResult = await pgClient.query(
            `SELECT c.chatbot_prompt, m.model_name, c.chatbot_id
             FROM chatbots c
             LEFT JOIN models m ON c.model_id = m.model_id
             WHERE c.chatbot_id = $1 AND c.user_id = $2 AND c.is_deleted = FALSE`,
            [chatbotId, userId],
          );

          if (chatbotResult.rows.length === 0) {
            throw new Error('Chatbot not found or access denied');
          }

          const chatbot = chatbotResult.rows[0];

          // 2. Load guardrails
          const guardrailsResult = await pgClient.query(
            `SELECT rule FROM guard_rulesets
             WHERE chatbot_id = $1
             ORDER BY order_index ASC`,
            [chatbotId],
          );

          // 3. Load enabled tool agents
          const toolAgentsResult = await pgClient.query(
            `SELECT tool_agent_key FROM chatbot_tool_agents
             WHERE chatbot_id = $1 AND is_enabled = TRUE`,
            [chatbotId],
          );

          // 4. Save user message to DB
          const userMsgResult = await pgClient.query(
            `INSERT INTO chatbot_messages (session_id, role, content)
             VALUES ($1, 'user', $2)
             RETURNING message_id, session_id, role, content, tool_calls, sources, elapsed_ms, created_at`,
            [sessionId, message],
          );

          const userMessage = userMsgResult.rows[0];

          // 5. Build system prompt with guardrails
          let combinedPrompt = '';
          const guardrails = guardrailsResult.rows.map((r: { rule: string }) => r.rule);

          if (guardrails.length > 0) {
            combinedPrompt += '[가드레일] 다음 규칙을 반드시 준수하세요:\n';
            combinedPrompt += guardrails.join('\n');
            combinedPrompt += '\n\n';
          }

          if (chatbot.chatbot_prompt) {
            combinedPrompt += chatbot.chatbot_prompt;
          }

          // 6. Build tool_agents array
          const toolAgents = toolAgentsResult.rows.map(
            (r: { tool_agent_key: string }) => r.tool_agent_key,
          );

          // 7. Call FastAPI Supervisor API
          const startTime = Date.now();
          let supervisorResponse: SupervisorResponse;

          try {
            const requestBody: Record<string, unknown> = {
              message,
              session_id: sessionId,
              tool_agents: toolAgents,
              model: chatbot.model_name || 'gpt-4o',
            };

            if (combinedPrompt.trim()) {
              requestBody.system_prompt = combinedPrompt;
            }

            const response = await fetch(
              `${DOMAIN_SERVER_URL}/agent/supervisor/chat`,
              {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(requestBody),
              },
            );

            if (!response.ok) {
              throw new Error(
                `Supervisor API error: ${response.status} ${response.statusText}`,
              );
            }

            supervisorResponse = await response.json();
          } catch (error: any) {
            // Save error as bot message
            const elapsedMs = Date.now() - startTime;
            const errorContent =
              error.message || '서버 연결에 실패했습니다. 잠시 후 다시 시도해주세요.';

            const errorMsgResult = await pgClient.query(
              `INSERT INTO chatbot_messages (session_id, role, content, elapsed_ms)
               VALUES ($1, 'bot', $2, $3)
               RETURNING message_id, session_id, role, content, tool_calls, sources, elapsed_ms, created_at`,
              [sessionId, errorContent, elapsedMs],
            );

            const errorMessage = errorMsgResult.rows[0];

            return {
              userMessage: formatMessage(userMessage),
              botMessage: formatMessage(errorMessage),
            };
          }

          // 8. Save bot message to DB (including tool_calls, sources, elapsed_ms)
          const elapsedMs = Date.now() - startTime;
          const toolCalls = supervisorResponse.tool_calls || [];
          const sources = supervisorResponse.sources || [];

          const botMsgResult = await pgClient.query(
            `INSERT INTO chatbot_messages (session_id, role, content, tool_calls, sources, elapsed_ms)
             VALUES ($1, 'bot', $2, $3, $4, $5)
             RETURNING message_id, session_id, role, content, tool_calls, sources, elapsed_ms, created_at`,
            [
              sessionId,
              supervisorResponse.response,
              toolCalls,
              sources,
              elapsedMs,
            ],
          );

          const botMessage = botMsgResult.rows[0];

          // 9. Return both messages
          return {
            userMessage: formatMessage(userMessage),
            botMessage: formatMessage(botMessage),
          };
        },
      },
    },
  };
});

function formatMessage(row: any) {
  return {
    messageId: row.message_id,
    sessionId: row.session_id,
    role: row.role,
    content: row.content,
    toolCalls: row.tool_calls || [],
    sources: row.sources || [],
    elapsedMs: row.elapsed_ms || null,
    createdAt: row.created_at ? row.created_at.toISOString() : null,
  };
}
