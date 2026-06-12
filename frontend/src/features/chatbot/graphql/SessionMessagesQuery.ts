import { graphql } from 'react-relay';

export const SessionMessagesQuery = graphql`
  query SessionMessagesQuery($sessionId: String!) {
    chatbotSessionBySessionId(sessionId: $sessionId) {
      id
      sessionId
      title
      chatbotMessagesBySessionId(orderBy: CREATED_AT_ASC) {
        nodes {
          id
          messageId
          role
          content
          toolCalls
          sources
          elapsedMs
          createdAt
        }
      }
    }
  }
`;
