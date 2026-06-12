import { graphql } from 'react-relay';

export const DeleteGuardRulesetMutation = graphql`
  mutation DeleteGuardRulesetMutation($input: DeleteGuardRulesetByGuardRulesetIdInput!) {
    deleteGuardRulesetByGuardRulesetId(input: $input) {
      deletedGuardRulesetId
      guardRuleset {
        id
        guardRulesetId
      }
    }
  }
`;
