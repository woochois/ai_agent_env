import { graphql } from 'react-relay';

export const UpdateToolAgentMutation = graphql`
  mutation UpdateToolAgentMutation($input: UpdateChatbotToolAgentByIdInput!) {
    updateChatbotToolAgentById(input: $input) {
      chatbotToolAgent {
        id
        chatbotToolAgentId
        toolAgentKey
        isEnabled
      }
    }
  }
`;
