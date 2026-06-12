/**
 * @generated SignedSource<<21ba0d3544a39385d2438a73aa355201>>
 * @lightSyntaxTransform
 * @nogrep
 */

/* tslint:disable */
/* eslint-disable */
// @ts-nocheck

import { ConcreteRequest, Mutation } from 'relay-runtime';
export type SendChatInput = {
  chatbotId: number;
  message: string;
  sessionId: string;
};
export type SendChatMutation$variables = {
  input: SendChatInput;
};
export type SendChatMutation$data = {
  readonly sendChat: {
    readonly botMessage: {
      readonly content: string;
      readonly createdAt: any | null | undefined;
      readonly elapsedMs: number | null | undefined;
      readonly id: string;
      readonly messageId: number;
      readonly role: string;
      readonly sessionId: string;
      readonly sources: ReadonlyArray<string | null | undefined> | null | undefined;
      readonly toolCalls: ReadonlyArray<string | null | undefined> | null | undefined;
    };
    readonly userMessage: {
      readonly content: string;
      readonly createdAt: any | null | undefined;
      readonly elapsedMs: number | null | undefined;
      readonly id: string;
      readonly messageId: number;
      readonly role: string;
      readonly sessionId: string;
      readonly sources: ReadonlyArray<string | null | undefined> | null | undefined;
      readonly toolCalls: ReadonlyArray<string | null | undefined> | null | undefined;
    };
  } | null | undefined;
};
export type SendChatMutation = {
  response: SendChatMutation$data;
  variables: SendChatMutation$variables;
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
    "args": null,
    "kind": "ScalarField",
    "name": "id",
    "storageKey": null
  },
  {
    "alias": null,
    "args": null,
    "kind": "ScalarField",
    "name": "messageId",
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
    "name": "role",
    "storageKey": null
  },
  {
    "alias": null,
    "args": null,
    "kind": "ScalarField",
    "name": "content",
    "storageKey": null
  },
  {
    "alias": null,
    "args": null,
    "kind": "ScalarField",
    "name": "toolCalls",
    "storageKey": null
  },
  {
    "alias": null,
    "args": null,
    "kind": "ScalarField",
    "name": "sources",
    "storageKey": null
  },
  {
    "alias": null,
    "args": null,
    "kind": "ScalarField",
    "name": "elapsedMs",
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
v2 = [
  {
    "alias": null,
    "args": [
      {
        "kind": "Variable",
        "name": "input",
        "variableName": "input"
      }
    ],
    "concreteType": "SendChatPayload",
    "kind": "LinkedField",
    "name": "sendChat",
    "plural": false,
    "selections": [
      {
        "alias": null,
        "args": null,
        "concreteType": "ChatbotMessage",
        "kind": "LinkedField",
        "name": "userMessage",
        "plural": false,
        "selections": (v1/*: any*/),
        "storageKey": null
      },
      {
        "alias": null,
        "args": null,
        "concreteType": "ChatbotMessage",
        "kind": "LinkedField",
        "name": "botMessage",
        "plural": false,
        "selections": (v1/*: any*/),
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
    "name": "SendChatMutation",
    "selections": (v2/*: any*/),
    "type": "Mutation",
    "abstractKey": null
  },
  "kind": "Request",
  "operation": {
    "argumentDefinitions": (v0/*: any*/),
    "kind": "Operation",
    "name": "SendChatMutation",
    "selections": (v2/*: any*/)
  },
  "params": {
    "cacheID": "904322c5daf3ea24fe20da1b106855ba",
    "id": null,
    "metadata": {},
    "name": "SendChatMutation",
    "operationKind": "mutation",
    "text": "mutation SendChatMutation(\n  $input: SendChatInput!\n) {\n  sendChat(input: $input) {\n    userMessage {\n      id\n      messageId\n      sessionId\n      role\n      content\n      toolCalls\n      sources\n      elapsedMs\n      createdAt\n    }\n    botMessage {\n      id\n      messageId\n      sessionId\n      role\n      content\n      toolCalls\n      sources\n      elapsedMs\n      createdAt\n    }\n  }\n}\n"
  }
};
})();

(node as any).hash = "4e290e1e6404d1c101de3dcf9b64fff8";

export default node;
