/**
 * @generated SignedSource<<c8d3256f1ef57353ed6edce8b0d9955f>>
 * @lightSyntaxTransform
 * @nogrep
 */

/* tslint:disable */
/* eslint-disable */
// @ts-nocheck

import { ConcreteRequest, Query } from 'relay-runtime';
export type SessionMessagesQuery$variables = {
  sessionId: string;
};
export type SessionMessagesQuery$data = {
  readonly chatbotSessionBySessionId: {
    readonly chatbotMessagesBySessionId: {
      readonly nodes: ReadonlyArray<{
        readonly content: string;
        readonly createdAt: any | null | undefined;
        readonly elapsedMs: number | null | undefined;
        readonly id: string;
        readonly messageId: number;
        readonly role: string;
        readonly sources: ReadonlyArray<string | null | undefined> | null | undefined;
        readonly toolCalls: ReadonlyArray<string | null | undefined> | null | undefined;
      }>;
    };
    readonly id: string;
    readonly sessionId: string;
    readonly title: string;
  } | null | undefined;
};
export type SessionMessagesQuery = {
  response: SessionMessagesQuery$data;
  variables: SessionMessagesQuery$variables;
};

const node: ConcreteRequest = (function(){
var v0 = [
  {
    "defaultValue": null,
    "kind": "LocalArgument",
    "name": "sessionId"
  }
],
v1 = {
  "alias": null,
  "args": null,
  "kind": "ScalarField",
  "name": "id",
  "storageKey": null
},
v2 = [
  {
    "alias": null,
    "args": [
      {
        "kind": "Variable",
        "name": "sessionId",
        "variableName": "sessionId"
      }
    ],
    "concreteType": "ChatbotSession",
    "kind": "LinkedField",
    "name": "chatbotSessionBySessionId",
    "plural": false,
    "selections": [
      (v1/*: any*/),
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
        "args": [
          {
            "kind": "Literal",
            "name": "orderBy",
            "value": "CREATED_AT_ASC"
          }
        ],
        "concreteType": "ChatbotMessagesConnection",
        "kind": "LinkedField",
        "name": "chatbotMessagesBySessionId",
        "plural": false,
        "selections": [
          {
            "alias": null,
            "args": null,
            "concreteType": "ChatbotMessage",
            "kind": "LinkedField",
            "name": "nodes",
            "plural": true,
            "selections": [
              (v1/*: any*/),
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
            "storageKey": null
          }
        ],
        "storageKey": "chatbotMessagesBySessionId(orderBy:\"CREATED_AT_ASC\")"
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
    "name": "SessionMessagesQuery",
    "selections": (v2/*: any*/),
    "type": "Query",
    "abstractKey": null
  },
  "kind": "Request",
  "operation": {
    "argumentDefinitions": (v0/*: any*/),
    "kind": "Operation",
    "name": "SessionMessagesQuery",
    "selections": (v2/*: any*/)
  },
  "params": {
    "cacheID": "40cd62c92d3f4b4eed9ec693de52431c",
    "id": null,
    "metadata": {},
    "name": "SessionMessagesQuery",
    "operationKind": "query",
    "text": "query SessionMessagesQuery(\n  $sessionId: String!\n) {\n  chatbotSessionBySessionId(sessionId: $sessionId) {\n    id\n    sessionId\n    title\n    chatbotMessagesBySessionId(orderBy: CREATED_AT_ASC) {\n      nodes {\n        id\n        messageId\n        role\n        content\n        toolCalls\n        sources\n        elapsedMs\n        createdAt\n      }\n    }\n  }\n}\n"
  }
};
})();

(node as any).hash = "2db71bccb974975956c774cd3a03236c";

export default node;
