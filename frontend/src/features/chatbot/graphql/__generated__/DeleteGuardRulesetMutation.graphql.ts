/**
 * @generated SignedSource<<62de683736baf96dae783d705ba7c364>>
 * @lightSyntaxTransform
 * @nogrep
 */

/* tslint:disable */
/* eslint-disable */
// @ts-nocheck

import { ConcreteRequest, Mutation } from 'relay-runtime';
export type DeleteGuardRulesetByGuardRulesetIdInput = {
  clientMutationId?: string | null | undefined;
  guardRulesetId: number;
};
export type DeleteGuardRulesetMutation$variables = {
  input: DeleteGuardRulesetByGuardRulesetIdInput;
};
export type DeleteGuardRulesetMutation$data = {
  readonly deleteGuardRulesetByGuardRulesetId: {
    readonly deletedGuardRulesetId: string | null | undefined;
    readonly guardRuleset: {
      readonly guardRulesetId: number;
      readonly id: string;
    } | null | undefined;
  } | null | undefined;
};
export type DeleteGuardRulesetMutation = {
  response: DeleteGuardRulesetMutation$data;
  variables: DeleteGuardRulesetMutation$variables;
};

const node: ConcreteRequest = (function(){
var v0 = [
  {
    "defaultValue": null,
    "kind": "LocalArgument",
    "name": "input"
  }
],
v1 = [
  {
    "alias": null,
    "args": [
      {
        "kind": "Variable",
        "name": "input",
        "variableName": "input"
      }
    ],
    "concreteType": "DeleteGuardRulesetPayload",
    "kind": "LinkedField",
    "name": "deleteGuardRulesetByGuardRulesetId",
    "plural": false,
    "selections": [
      {
        "alias": null,
        "args": null,
        "kind": "ScalarField",
        "name": "deletedGuardRulesetId",
        "storageKey": null
      },
      {
        "alias": null,
        "args": null,
        "concreteType": "GuardRuleset",
        "kind": "LinkedField",
        "name": "guardRuleset",
        "plural": false,
        "selections": [
          {
            "alias": null,
            "args": null,
            "kind": "ScalarField",
            "name": "id",
            "storageKey": null
          },
          {
            "alias": null,
            "args": null,
            "kind": "ScalarField",
            "name": "guardRulesetId",
            "storageKey": null
          }
        ],
        "storageKey": null
      }
    ],
    "storageKey": null
  }
];
return {
  "fragment": {
    "argumentDefinitions": (v0/*: any*/),
    "kind": "Fragment",
    "metadata": null,
    "name": "DeleteGuardRulesetMutation",
    "selections": (v1/*: any*/),
    "type": "Mutation",
    "abstractKey": null
  },
  "kind": "Request",
  "operation": {
    "argumentDefinitions": (v0/*: any*/),
    "kind": "Operation",
    "name": "DeleteGuardRulesetMutation",
    "selections": (v1/*: any*/)
  },
  "params": {
    "cacheID": "26252fd2f32c43e894cab5e7c31e31e8",
    "id": null,
    "metadata": {},
    "name": "DeleteGuardRulesetMutation",
    "operationKind": "mutation",
    "text": "mutation DeleteGuardRulesetMutation(\n  $input: DeleteGuardRulesetByGuardRulesetIdInput!\n) {\n  deleteGuardRulesetByGuardRulesetId(input: $input) {\n    deletedGuardRulesetId\n    guardRuleset {\n      id\n      guardRulesetId\n    }\n  }\n}\n"
  }
};
})();

(node as any).hash = "312971217c5bcaa94920a685b9146008";

export default node;
