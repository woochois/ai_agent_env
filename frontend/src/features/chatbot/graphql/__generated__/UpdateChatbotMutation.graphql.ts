/**
 * @generated SignedSource<<53f331c788596a0c7f1290ba6d650688>>
 * @lightSyntaxTransform
 * @nogrep
 */

/* tslint:disable */
/* eslint-disable */
// @ts-nocheck

import { ConcreteRequest, Mutation } from 'relay-runtime';
export type UpdateChatbotByChatbotIdInput = {
  chatbotId: number;
  chatbotPatch: ChatbotPatch;
  clientMutationId?: string | null | undefined;
};
export type ChatbotPatch = {
  chatbotPluginKey?: string | null | undefined;
  chatbotPrompt?: string | null | undefined;
  chatbotTitle?: string | null | undefined;
  chatbotVisibility?: boolean | null | undefined;
  description?: string | null | undefined;
  modelId?: number | null | undefined;
};
export type UpdateChatbotMutation$variables = {
  input: UpdateChatbotByChatbotIdInput;
};
export type UpdateChatbotMutation$data = {
  readonly updateChatbotByChatbotId: {
    readonly chatbot: {
      readonly chatbotId: number;
      readonly chatbotPrompt: string | null | undefined;
      readonly chatbotTitle: string;
      readonly description: string | null | undefined;
      readonly id: string;
      readonly modelId: number | null | undefined;
    } | null | undefined;
  } | null | undefined;
};
export type UpdateChatbotMutation = {
  response: UpdateChatbotMutation$data;
  variables: UpdateChatbotMutation$variables;
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
    "concreteType": "UpdateChatbotPayload",
    "kind": "LinkedField",
    "name": "updateChatbotByChatbotId",
    "plural": false,
    "selections": [
      {
        "alias": null,
        "args": null,
        "concreteType": "Chatbot",
        "kind": "LinkedField",
        "name": "chatbot",
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
            "name": "chatbotId",
            "storageKey": null
          },
          {
            "alias": null,
            "args": null,
            "kind": "ScalarField",
            "name": "chatbotTitle",
            "storageKey": null
          },
          {
            "alias": null,
            "args": null,
            "kind": "ScalarField",
            "name": "description",
            "storageKey": null
          },
          {
            "alias": null,
            "args": null,
            "kind": "ScalarField",
            "name": "chatbotPrompt",
            "storageKey": null
          },
          {
            "alias": null,
            "args": null,
            "kind": "ScalarField",
            "name": "modelId",
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
    "name": "UpdateChatbotMutation",
    "selections": (v1/*: any*/),
    "type": "Mutation",
    "abstractKey": null
  },
  "kind": "Request",
  "operation": {
    "argumentDefinitions": (v0/*: any*/),
    "kind": "Operation",
    "name": "UpdateChatbotMutation",
    "selections": (v1/*: any*/)
  },
  "params": {
    "cacheID": "c3629b18482069142b8e3405d047a83a",
    "id": null,
    "metadata": {},
    "name": "UpdateChatbotMutation",
    "operationKind": "mutation",
    "text": "mutation UpdateChatbotMutation(\n  $input: UpdateChatbotByChatbotIdInput!\n) {\n  updateChatbotByChatbotId(input: $input) {\n    chatbot {\n      id\n      chatbotId\n      chatbotTitle\n      description\n      chatbotPrompt\n      modelId\n    }\n  }\n}\n"
  }
};
})();

(node as any).hash = "ca14005372a3760a01cd58040f98ce7e";

export default node;
