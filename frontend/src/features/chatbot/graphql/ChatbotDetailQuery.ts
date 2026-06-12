import { graphql } from 'react-relay';

export const ChatbotDetailQuery = graphql`
  query ChatbotDetailQuery($chatbotId: Int!) {
    chatbotByChatbotId(chatbotId: $chatbotId) {
      id
      chatbotId
      chatbotTitle
      description
      chatbotPrompt
      modelId
      chatbotSessionsByChatbotId(
        filter: { isDeleted: { equalTo: false } }
        orderBy: CREATED_AT_DESC
        first: 50
      ) {
        nodes {
          id
          sessionId
          title
          createdAt
        }
      }
      guardRulesetsByChatbotId(orderBy: ORDER_INDEX_ASC) {
        nodes {
          id
          guardRulesetId
          rule
          orderIndex
        }
      }
      chatbotToolAgentsByChatbotId {
        nodes {
          id
          chatbotToolAgentId
          toolAgentKey
          isEnabled
        }
      }
    }
  }
`;
