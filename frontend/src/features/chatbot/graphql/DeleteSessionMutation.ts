import { graphql } from 'react-relay';

export const DeleteSessionMutation = graphql`
  mutation DeleteSessionMutation($input: DeleteChatbotSessionBySessionIdInput!) {
    deleteChatbotSessionBySessionId(input: $input) {
      deletedChatbotSessionId
    }
  }
`;
