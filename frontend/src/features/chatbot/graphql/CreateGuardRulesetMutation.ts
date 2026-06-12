import { graphql } from 'react-relay';

export const CreateGuardRulesetMutation = graphql`
  mutation CreateGuardRulesetMutation($input: CreateGuardRulesetInput!) {
    createGuardRuleset(input: $input) {
      guardRuleset {
        id
        guardRulesetId
        chatbotId
        rule
        orderIndex
      }
    }
  }
`;
