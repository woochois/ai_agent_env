import { graphql } from 'react-relay';

export const UpdateChatbotMutation = graphql`
  mutation UpdateChatbotMutation($input: UpdateChatbotByChatbotIdInput!) {
    updateChatbotByChatbotId(input: $input) {
      chatbot {
        id
        chatbotId
        chatbotTitle
        description
        chatbotPrompt
        modelId
      }
    }
  }
`;
