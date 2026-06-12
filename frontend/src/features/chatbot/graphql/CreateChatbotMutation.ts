import { graphql } from 'react-relay';

export const CreateChatbotMutation = graphql`
  mutation CreateChatbotMutation($input: CreateChatbotInput!) {
    createChatbot(input: $input) {
      chatbot {
        id
        chatbotId
        chatbotTitle
        description
        createdAt
      }
    }
  }
`;
