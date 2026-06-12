import { graphql } from 'react-relay';

export const ChatbotListQuery = graphql`
  query ChatbotListQuery($userId: Int!, $isDeleted: BooleanFilter) {
    allChatbots(
      filter: { userId: { equalTo: $userId }, isDeleted: $isDeleted }
      orderBy: CREATED_AT_DESC
    ) {
      nodes {
        id
        chatbotId
        chatbotTitle
        description
        createdAt
      }
    }
  }
`;
