/**
 * @generated SignedSource<<74ffeb6b5674484b01913976ac7b68d8>>
 * @lightSyntaxTransform
 * @nogrep
 */

/* tslint:disable */
/* eslint-disable */
// @ts-nocheck

import { ConcreteRequest, Query } from 'relay-runtime';
export type BooleanFilter = {
  equalTo?: boolean | null | undefined;
  isNull?: boolean | null | undefined;
  notEqualTo?: boolean | null | undefined;
};
export type ChatbotListQuery$variables = {
  isDeleted?: BooleanFilter | null | undefined;
  userId: number;
};
export type ChatbotListQuery$data = {
  readonly allChatbots: {
    readonly nodes: ReadonlyArray<{
      readonly chatbotId: number;
      readonly chatbotTitle: string;
      readonly createdAt: any | null | undefined;
      readonly description: string | null | undefined;
      readonly id: string;
    }>;
  } | null | undefined;
};
export type ChatbotListQuery = {
  response: ChatbotListQuery$data;
  variables: ChatbotListQuery$variables;
};

const node: ConcreteRequest = (function(){
var v0 = {
  "defaultValue": null,
  "kind": "LocalArgument",
  "name": "isDeleted"
},
v1 = {
  "defaultValue": null,
  "kind": "LocalArgument",
  "name": "userId"
},
v2 = [
  {
    "alias": null,
    "args": [
      {
        "fields": [
          {
            "kind": "Variable",
            "name": "isDeleted",
            "variableName": "isDeleted"
          },
          {
            "fields": [
              {
                "kind": "Variable",
                "name": "equalTo",
                "variableName": "userId"
              }
            ],
            "kind": "ObjectValue",
            "name": "userId"
          }
        ],
        "kind": "ObjectValue",
        "name": "filter"
      },
      {
        "kind": "Literal",
        "name": "orderBy",
        "value": "CREATED_AT_DESC"
      }
    ],
    "concreteType": "ChatbotsConnection",
    "kind": "LinkedField",
    "name": "allChatbots",
    "plural": false,
    "selections": [
      {
        "alias": null,
        "args": null,
        "concreteType": "Chatbot",
        "kind": "LinkedField",
        "name": "nodes",
        "plural": true,
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
    "argumentDefinitions": [
      (v0/*: any*/),
      (v1/*: any*/)
    ],
    "kind": "Fragment",
    "metadata": null,
    "name": "ChatbotListQuery",
    "selections": (v2/*: any*/),
    "type": "Query",
    "abstractKey": null
  },
  "kind": "Request",
  "operation": {
    "argumentDefinitions": [
      (v1/*: any*/),
      (v0/*: any*/)
    ],
    "kind": "Operation",
    "name": "ChatbotListQuery",
    "selections": (v2/*: any*/)
  },
  "params": {
    "cacheID": "cd0e3370bb4134cac339ee1290bdc3b2",
    "id": null,
    "metadata": {},
    "name": "ChatbotListQuery",
    "operationKind": "query",
    "text": "query ChatbotListQuery(\n  $userId: Int!\n  $isDeleted: BooleanFilter\n) {\n  allChatbots(filter: {userId: {equalTo: $userId}, isDeleted: $isDeleted}, orderBy: CREATED_AT_DESC) {\n    nodes {\n      id\n      chatbotId\n      chatbotTitle\n      description\n      createdAt\n    }\n  }\n}\n"
  }
};
})();

(node as any).hash = "0b95e866ca540d644ae109d0b27c07c7";

export default node;
