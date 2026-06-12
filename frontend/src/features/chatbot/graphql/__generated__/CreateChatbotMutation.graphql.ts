/**
 * @generated SignedSource<<8f368238f3339f0f9d2bb327df1e8220>>
 * @lightSyntaxTransform
 * @nogrep
 */

/* tslint:disable */
/* eslint-disable */
// @ts-nocheck

import { ConcreteRequest, Mutation } from 'relay-runtime';
export type CreateChatbotInput = {
  chatbot: ChatbotInput;
  clientMutationId?: string | null | undefined;
};
export type ChatbotInput = {
  chatbotPluginKey?: string | null | undefined;
  chatbotPrompt?: string | null | undefined;
  chatbotTitle: string;
  chatbotVisibility?: boolean | null | undefined;
  description?: string | null | undefined;
  modelId?: number | null | undefined;
  userId: number;
};
export type CreateChatbotMutation$variables = {
  input: CreateChatbotInput;
};
export type CreateChatbotMutation$data = {
  readonly createChatbot: {
    readonly chatbot: {
      readonly chatbotId: number;
      readonly chatbotTitle: string;
      readonly createdAt: any | null | undefined;
      readonly description: string | null | undefined;
      readonly id: string;
    } | null | undefined;
  } | null | undefined;
};
export type CreateChatbotMutation = {
  response: CreateChatbotMutation$data;
  variables: CreateChatbotMutation$variables;
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
    "concreteType": "CreateChatbotPayload",
    "kind": "LinkedField",
    "name": "createChatbot",
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
            "name": "createdAt",
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
    "name": "CreateChatbotMutation",
    "selections": (v1/*: any*/),
    "type": "Mutation",
    "abstractKey": null
  },
  "kind": "Request",
  "operation": {
    "argumentDefinitions": (v0/*: any*/),
    "kind": "Operation",
    "name": "CreateChatbotMutation",
    "selections": (v1/*: any*/)
  },
  "params": {
    "cacheID": "0048c7119021167fd6c8af709c0c6752",
    "id": null,
    "metadata": {},
    "name": "CreateChatbotMutation",
    "operationKind": "mutation",
    "text": "mutation CreateChatbotMutation(\n  $input: CreateChatbotInput!\n) {\n  createChatbot(input: $input) {\n    chatbot {\n      id\n      chatbotId\n      chatbotTitle\n      description\n      createdAt\n    }\n  }\n}\n"
  }
};
})();

(node as any).hash = "314f60227e358342d5f711983f4cbc4a";

export default node;
