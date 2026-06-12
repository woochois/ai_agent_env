/**
 * @generated SignedSource<<76831ff6da36fb3d5bdcfbc38e1513d1>>
 * @lightSyntaxTransform
 * @nogrep
 */

/* tslint:disable */
/* eslint-disable */
// @ts-nocheck

import { ConcreteRequest, Mutation } from 'relay-runtime';
export type CreateChatbotSessionInput = {
  chatbotSession: ChatbotSessionInput;
  clientMutationId?: string | null | undefined;
};
export type ChatbotSessionInput = {
  chatbotId: number;
  sessionId?: string | null | undefined;
  title?: string | null | undefined;
  userId: number;
};
export type CreateSessionMutation$variables = {
  input: CreateChatbotSessionInput;
};
export type CreateSessionMutation$data = {
  readonly createChatbotSession: {
    readonly chatbotSession: {
      readonly createdAt: any | null | undefined;
      readonly id: string;
      readonly sessionId: string;
      readonly title: string;
    } | null | undefined;
  } | null | undefined;
};
export type CreateSessionMutation = {
  response: CreateSessionMutation$data;
  variables: CreateSessionMutation$variables;
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
    "concreteType": "CreateChatbotSessionPayload",
    "kind": "LinkedField",
    "name": "createChatbotSession",
    "plural": false,
    "selections": [
      {
        "alias": null,
        "args": null,
        "concreteType": "ChatbotSession",
        "kind": "LinkedField",
        "name": "chatbotSession",
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
            "name": "sessionId",
            "storageKey": null
          },
          {
            "alias": null,
            "args": null,
            "kind": "ScalarField",
            "name": "title",
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
    "name": "CreateSessionMutation",
    "selections": (v1/*: any*/),
    "type": "Mutation",
    "abstractKey": null
  },
  "kind": "Request",
  "operation": {
    "argumentDefinitions": (v0/*: any*/),
    "kind": "Operation",
    "name": "CreateSessionMutation",
    "selections": (v1/*: any*/)
  },
  "params": {
    "cacheID": "1724794ba2fc61127eb1bcf1314cb269",
    "id": null,
    "metadata": {},
    "name": "CreateSessionMutation",
    "operationKind": "mutation",
    "text": "mutation CreateSessionMutation(\n  $input: CreateChatbotSessionInput!\n) {\n  createChatbotSession(input: $input) {\n    chatbotSession {\n      id\n      sessionId\n      title\n      createdAt\n    }\n  }\n}\n"
  }
};
})();

(node as any).hash = "c2e4efdc2b050c923f4cb3acbfbe7e30";

export default node;
