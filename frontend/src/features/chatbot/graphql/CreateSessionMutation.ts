import { graphql } from 'react-relay';

export const CreateSessionMutation = graphql`
  mutation CreateSessionMutation($input: CreateChatbotSessionInput!) {
    createChatbotSession(input: $input) {
      chatbotSession {
        id
        sessionId
        title
        createdAt
      }
    }
  }
`;
