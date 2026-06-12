/**
 * @generated SignedSource<<a2172cbd655ffb33e458f71de0fce928>>
 * @lightSyntaxTransform
 * @nogrep
 */

/* tslint:disable */
/* eslint-disable */
// @ts-nocheck

import { ConcreteRequest, Mutation } from 'relay-runtime';
export type DeleteChatbotByChatbotIdInput = {
  chatbotId: number;
  clientMutationId?: string | null | undefined;
};
export type DeleteChatbotMutation$variables = {
  input: DeleteChatbotByChatbotIdInput;
};
export type DeleteChatbotMutation$data = {
  readonly deleteChatbotByChatbotId: {
    readonly chatbot: {
      readonly chatbotId: number;
      readonly id: string;
    } | null | undefined;
    readonly deletedChatbotId: string | null | undefined;
  } | null | undefined;
};
export type DeleteChatbotMutation = {
  response: DeleteChatbotMutation$data;
  variables: DeleteChatbotMutation$variables;
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
    "concreteType": "DeleteChatbotPayload",
    "kind": "LinkedField",
    "name": "deleteChatbotByChatbotId",
    "plural": false,
    "selections": [
      {
        "alias": null,
        "args": null,
        "kind": "ScalarField",
        "name": "deletedChatbotId",
        "storageKey": null
      },
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
    "name": "DeleteChatbotMutation",
    "selections": (v1/*: any*/),
    "type": "Mutation",
    "abstractKey": null
  },
  "kind": "Request",
  "operation": {
    "argumentDefinitions": (v0/*: any*/),
    "kind": "Operation",
    "name": "DeleteChatbotMutation",
    "selections": (v1/*: any*/)
  },
  "params": {
    "cacheID": "23368523701157adc7c8e0f2f3fc3603",
    "id": null,
    "metadata": {},
    "name": "DeleteChatbotMutation",
    "operationKind": "mutation",
    "text": "mutation DeleteChatbotMutation(\n  $input: DeleteChatbotByChatbotIdInput!\n) {\n  deleteChatbotByChatbotId(input: $input) {\n    deletedChatbotId\n    chatbot {\n      id\n      chatbotId\n    }\n  }\n}\n"
  }
};
})();

(node as any).hash = "02eba4ea621dbe68ff2ca9966325bc47";

export default node;
