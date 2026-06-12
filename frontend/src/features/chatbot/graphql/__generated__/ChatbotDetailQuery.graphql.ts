/**
 * @generated SignedSource<<a5361b2dd4e1b6ce0853d4d54b98d31f>>
 * @lightSyntaxTransform
 * @nogrep
 */

/* tslint:disable */
/* eslint-disable */
// @ts-nocheck

import { ConcreteRequest, Query } from 'relay-runtime';
export type ChatbotDetailQuery$variables = {
  chatbotId: number;
};
export type ChatbotDetailQuery$data = {
  readonly chatbotByChatbotId: {
    readonly chatbotId: number;
    readonly chatbotPrompt: string | null | undefined;
    readonly chatbotSessionsByChatbotId: {
      readonly nodes: ReadonlyArray<{
        readonly createdAt: any | null | undefined;
        readonly id: string;
        readonly sessionId: string;
        readonly title: string;
      }>;
    };
    readonly chatbotTitle: string;
    readonly chatbotToolAgentsByChatbotId: {
      readonly nodes: ReadonlyArray<{
        readonly chatbotToolAgentId: number;
        readonly id: string;
        readonly isEnabled: boolean;
        readonly toolAgentKey: string;
      }>;
    };
    readonly description: string | null | undefined;
    readonly guardRulesetsByChatbotId: {
      readonly nodes: ReadonlyArray<{
        readonly guardRulesetId: number;
        readonly id: string;
        readonly orderIndex: number;
        readonly rule: string;
      }>;
    };
    readonly id: string;
    readonly modelId: number | null | undefined;
  } | null | undefined;
};
export type ChatbotDetailQuery = {
  response: ChatbotDetailQuery$data;
  variables: ChatbotDetailQuery$variables;
};

const node: ConcreteRequest = (function(){
var v0 = [
  {
    "defaultValue": null,
    "kind": "LocalArgument",
    "name": "chatbotId"
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
        "name": "chatbotId",
        "variableName": "chatbotId"
      }
    ],
    "concreteType": "Chatbot",
    "kind": "LinkedField",
    "name": "chatbotByChatbotId",
    "plural": false,
    "selections": [
      (v1/*: any*/),
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
      },
      {
        "alias": null,
        "args": [
          {
            "kind": "Literal",
            "name": "filter",
            "value": {
              "isDeleted": {
                "equalTo": false
              }
            }
          },
          {
            "kind": "Literal",
            "name": "first",
            "value": 50
          },
          {
            "kind": "Literal",
            "name": "orderBy",
            "value": "CREATED_AT_DESC"
          }
        ],
        "concreteType": "ChatbotSessionsConnection",
        "kind": "LinkedField",
        "name": "chatbotSessionsByChatbotId",
        "plural": false,
        "selections": [
          {
            "alias": null,
            "args": null,
            "concreteType": "ChatbotSession",
            "kind": "LinkedField",
            "name": "nodes",
            "plural": true,
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
                "args": null,
                "kind": "ScalarField",
                "name": "createdAt",
                "storageKey": null
              }
            ],
            "storageKey": null
          }
        ],
        "storageKey": "chatbotSessionsByChatbotId(filter:{\"isDeleted\":{\"equalTo\":false}},first:50,orderBy:\"CREATED_AT_DESC\")"
      },
      {
        "alias": null,
        "args": [
          {
            "kind": "Literal",
            "name": "orderBy",
            "value": "ORDER_INDEX_ASC"
          }
        ],
        "concreteType": "GuardRulesetsConnection",
        "kind": "LinkedField",
        "name": "guardRulesetsByChatbotId",
        "plural": false,
        "selections": [
          {
            "alias": null,
            "args": null,
            "concreteType": "GuardRuleset",
            "kind": "LinkedField",
            "name": "nodes",
            "plural": true,
            "selections": [
              (v1/*: any*/),
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
        "storageKey": "guardRulesetsByChatbotId(orderBy:\"ORDER_INDEX_ASC\")"
      },
      {
        "alias": null,
        "args": null,
        "concreteType": "ChatbotToolAgentsConnection",
        "kind": "LinkedField",
        "name": "chatbotToolAgentsByChatbotId",
        "plural": false,
        "selections": [
          {
            "alias": null,
            "args": null,
            "concreteType": "ChatbotToolAgent",
            "kind": "LinkedField",
            "name": "nodes",
            "plural": true,
            "selections": [
              (v1/*: any*/),
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
    ],
    "storageKey": null
  }
];
return {
  "fragment": {
    "argumentDefinitions": (v0/*: any*/),
    "kind": "Fragment",
    "metadata": null,
    "name": "ChatbotDetailQuery",
    "selections": (v2/*: any*/),
    "type": "Query",
    "abstractKey": null
  },
  "kind": "Request",
  "operation": {
    "argumentDefinitions": (v0/*: any*/),
    "kind": "Operation",
    "name": "ChatbotDetailQuery",
    "selections": (v2/*: any*/)
  },
  "params": {
    "cacheID": "26a761c6c726b62ad885b9745c9e3d4c",
    "id": null,
    "metadata": {},
    "name": "ChatbotDetailQuery",
    "operationKind": "query",
    "text": "query ChatbotDetailQuery(\n  $chatbotId: Int!\n) {\n  chatbotByChatbotId(chatbotId: $chatbotId) {\n    id\n    chatbotId\n    chatbotTitle\n    description\n    chatbotPrompt\n    modelId\n    chatbotSessionsByChatbotId(filter: {isDeleted: {equalTo: false}}, orderBy: CREATED_AT_DESC, first: 50) {\n      nodes {\n        id\n        sessionId\n        title\n        createdAt\n      }\n    }\n    guardRulesetsByChatbotId(orderBy: ORDER_INDEX_ASC) {\n      nodes {\n        id\n        guardRulesetId\n        rule\n        orderIndex\n      }\n    }\n    chatbotToolAgentsByChatbotId {\n      nodes {\n        id\n        chatbotToolAgentId\n        toolAgentKey\n        isEnabled\n      }\n    }\n  }\n}\n"
  }
};
})();

(node as any).hash = "e12631d1ae54b97bc95e3486cdc033ed";

export default node;
