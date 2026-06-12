/**
 * @generated SignedSource<<1d580e38b068359c77a798a402d66eb8>>
 * @lightSyntaxTransform
 * @nogrep
 */

/* tslint:disable */
/* eslint-disable */
// @ts-nocheck

import { ConcreteRequest, Mutation } from 'relay-runtime';
export type DeleteChatbotSessionBySessionIdInput = {
  clientMutationId?: string | null | undefined;
  sessionId: string;
};
export type DeleteSessionMutation$variables = {
  input: DeleteChatbotSessionBySessionIdInput;
};
export type DeleteSessionMutation$data = {
  readonly deleteChatbotSessionBySessionId: {
    readonly deletedChatbotSessionId: string | null | undefined;
  } | null | undefined;
};
export type DeleteSessionMutation = {
  response: DeleteSessionMutation$data;
  variables: DeleteSessionMutation$variables;
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
    "concreteType": "DeleteChatbotSessionPayload",
    "kind": "LinkedField",
    "name": "deleteChatbotSessionBySessionId",
    "plural": false,
    "selections": [
      {
        "alias": null,
        "args": null,
        "kind": "ScalarField",
        "name": "deletedChatbotSessionId",
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
    "name": "DeleteSessionMutation",
    "selections": (v1/*: any*/),
    "type": "Mutation",
    "abstractKey": null
  },
  "kind": "Request",
  "operation": {
    "argumentDefinitions": (v0/*: any*/),
    "kind": "Operation",
    "name": "DeleteSessionMutation",
    "selections": (v1/*: any*/)
  },
  "params": {
    "cacheID": "fdb5c23fb48a7dfdb0a3e52ec0541b7c",
    "id": null,
    "metadata": {},
    "name": "DeleteSessionMutation",
    "operationKind": "mutation",
    "text": "mutation DeleteSessionMutation(\n  $input: DeleteChatbotSessionBySessionIdInput!\n) {\n  deleteChatbotSessionBySessionId(input: $input) {\n    deletedChatbotSessionId\n  }\n}\n"
  }
};
})();

(node as any).hash = "f52aa2c65d0def0f5546f2f5ec1a531f";

export default node;
