/**
 * @generated SignedSource<<8d23e580d065d0339c17b1fbc069f499>>
 * @lightSyntaxTransform
 * @nogrep
 */

/* tslint:disable */
/* eslint-disable */
// @ts-nocheck

import { ConcreteRequest, Mutation } from 'relay-runtime';
export type CreateGuardRulesetInput = {
  clientMutationId?: string | null | undefined;
  guardRuleset: GuardRulesetInput;
};
export type GuardRulesetInput = {
  chatbotId: number;
  orderIndex: number;
  rule: string;
};
export type CreateGuardRulesetMutation$variables = {
  input: CreateGuardRulesetInput;
};
export type CreateGuardRulesetMutation$data = {
  readonly createGuardRuleset: {
    readonly guardRuleset: {
      readonly chatbotId: number;
      readonly guardRulesetId: number;
      readonly id: string;
      readonly orderIndex: number;
      readonly rule: string;
    } | null | undefined;
  } | null | undefined;
};
export type CreateGuardRulesetMutation = {
  response: CreateGuardRulesetMutation$data;
  variables: CreateGuardRulesetMutation$variables;
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
    "concreteType": "CreateGuardRulesetPayload",
    "kind": "LinkedField",
    "name": "createGuardRuleset",
    "plural": false,
    "selections": [
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
          },
          {
            "alias": null,
            "args": null,
            "kind": "ScalarField",
            "name": "chatbotId",
            "storageKey": null
          },
          {
            "alias": null,
            "args": null,
            "kind": "ScalarField",
            "name": "rule",
            "storageKey": null
          },
          {
            "alias": null,
            "args": null,
            "kind": "ScalarField",
            "name": "orderIndex",
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
    "name": "CreateGuardRulesetMutation",
    "selections": (v1/*: any*/),
    "type": "Mutation",
    "abstractKey": null
  },
  "kind": "Request",
  "operation": {
    "argumentDefinitions": (v0/*: any*/),
    "kind": "Operation",
    "name": "CreateGuardRulesetMutation",
    "selections": (v1/*: any*/)
  },
  "params": {
    "cacheID": "3cce454d41a7ae1e4be0b0a750af3e3b",
    "id": null,
    "metadata": {},
    "name": "CreateGuardRulesetMutation",
    "operationKind": "mutation",
    "text": "mutation CreateGuardRulesetMutation(\n  $input: CreateGuardRulesetInput!\n) {\n  createGuardRuleset(input: $input) {\n    guardRuleset {\n      id\n      guardRulesetId\n      chatbotId\n      rule\n      orderIndex\n    }\n  }\n}\n"
  }
};
})();

(node as any).hash = "29a6bcab16cf65a27347aba8f6ccdf5d";

export default node;
