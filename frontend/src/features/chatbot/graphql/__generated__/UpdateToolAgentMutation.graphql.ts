/**
 * @generated SignedSource<<f14b9b6676b316f38852c7d54ad5d641>>
 * @lightSyntaxTransform
 * @nogrep
 */

/* tslint:disable */
/* eslint-disable */
// @ts-nocheck

import { ConcreteRequest, Mutation } from 'relay-runtime';
export type UpdateChatbotToolAgentByIdInput = {
  chatbotToolAgentPatch: ChatbotToolAgentPatch;
  clientMutationId?: string | null | undefined;
  id: number;
};
export type ChatbotToolAgentPatch = {
  isEnabled?: boolean | null | undefined;
  toolAgentKey?: string | null | undefined;
};
export type UpdateToolAgentMutation$variables = {
  input: UpdateChatbotToolAgentByIdInput;
};
export type UpdateToolAgentMutation$data = {
  readonly updateChatbotToolAgentById: {
    readonly chatbotToolAgent: {
      readonly chatbotToolAgentId: number;
      readonly id: string;
      readonly isEnabled: boolean;
      readonly toolAgentKey: string;
    } | null | undefined;
  } | null | undefined;
};
export type UpdateToolAgentMutation = {
  response: UpdateToolAgentMutation$data;
  variables: UpdateToolAgentMutation$variables;
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
    "concreteType": "UpdateChatbotToolAgentPayload",
    "kind": "LinkedField",
    "name": "updateChatbotToolAgentById",
    "plural": false,
    "selections": [
      {
        "alias": null,
        "args": null,
        "concreteType": "ChatbotToolAgent",
        "kind": "LinkedField",
        "name": "chatbotToolAgent",
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
            "name": "chatbotToolAgentId",
            "storageKey": null
          },
          {
            "alias": null,
            "args": null,
            "kind": "ScalarField",
            "name": "toolAgentKey",
            "storageKey": null
          },
          {
            "alias": null,
            "args": null,
            "kind": "ScalarField",
            "name": "isEnabled",
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
    "name": "UpdateToolAgentMutation",
    "selections": (v1/*: any*/),
    "type": "Mutation",
    "abstractKey": null
  },
  "kind": "Request",
  "operation": {
    "argumentDefinitions": (v0/*: any*/),
    "kind": "Operation",
    "name": "UpdateToolAgentMutation",
    "selections": (v1/*: any*/)
  },
  "params": {
    "cacheID": "7dc6fe07f31f87c64d4948a7a0cf0c92",
    "id": null,
    "metadata": {},
    "name": "UpdateToolAgentMutation",
    "operationKind": "mutation",
    "text": "mutation UpdateToolAgentMutation(\n  $input: UpdateChatbotToolAgentByIdInput!\n) {\n  updateChatbotToolAgentById(input: $input) {\n    chatbotToolAgent {\n      id\n      chatbotToolAgentId\n      toolAgentKey\n      isEnabled\n    }\n  }\n}\n"
  }
};
})();

(node as any).hash = "b3fb02130798930aae3f374bac644719";

export default node;
