import { graphql } from 'react-relay';

export const DeleteChatbotMutation = graphql`
  mutation DeleteChatbotMutation($input: DeleteChatbotByChatbotIdInput!) {
    deleteChatbotByChatbotId(input: $input) {
      deletedChatbotId
      chatbot {
        id
        chatbotId
      }
    }
  }
`;
