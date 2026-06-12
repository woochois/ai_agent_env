import { graphql } from 'react-relay';

export const SendChatMutation = graphql`
  mutation SendChatMutation($input: SendChatInput!) {
    sendChat(input: $input) {
      userMessage {
        id
        messageId
        sessionId
        role
        content
        toolCalls
        sources
        elapsedMs
        createdAt
      }
      botMessage {
        id
        messageId
        sessionId
        role
        content
        toolCalls
        sources
        elapsedMs
        createdAt
      }
    }
  }
`;
