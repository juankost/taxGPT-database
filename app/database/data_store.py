import os
import firebase_admin
from firebase_admin import credentials
from firebase_admin import firestore
from dotenv import load_dotenv
from datetime import datetime


# Initialize the database
load_dotenv()
print(os.environ.get("GOOGLE_APPLICATION_CREDENTIALS"))
service_account_path = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
cred = credentials.Certificate(service_account_path)
firebase_admin.initialize_app(cred)
db = firestore.client()


# Operations on the database
def add_chat_history(user_id, chat_id, conversation):
    document_id = f"{user_id}-{chat_id}"
    doc_ref = db.collection("chat_histories").document(document_id)
    doc_ref.set(
        {
            "user_id": user_id,
            "chat_id": chat_id,
            "timestamp": firestore.SERVER_TIMESTAMP,
            "conversation": conversation,
        }
    )


def get_chat_history(user_id, chat_id):
    document_id = f"{user_id}-{chat_id}"
    doc_ref = db.collection("chat_histories").document(document_id)
    doc = doc_ref.get()
    if doc.exists:
        return doc.to_dict().get("conversation", [])
    else:
        return []


def append_to_chat_history(user_id, chat_id, message):
    document_id = f"{user_id}-{chat_id}"
    doc_ref = db.collection("chat_histories").document(document_id)

    # Perform a transaction to ensure that the append operation is atomic
    @firestore.transactional
    def append_in_transaction(transaction, doc_ref, message):
        snapshot = doc_ref.get(transaction=transaction)
        if snapshot.exists:
            current_conversation = snapshot.get("conversation")
            # Extend the existing conversation array with the new messages array
            if isinstance(message, list):
                current_conversation.extend(message)
                current_timestamp = datetime.utcnow()  # Update the timestamp
                transaction.update(doc_ref, {"conversation": current_conversation, "timestamp": current_timestamp})
            else:
                raise ValueError("New messages must be a list")
        else:
            # If the document does not exist, create it with the message as the first item
            # and set the initial timestamp
            initial_timestamp = datetime.utcnow()
            transaction.set(
                doc_ref,
                {
                    "user_id": user_id,
                    "chat_id": chat_id,
                    "conversation": message,
                    "timestamp": initial_timestamp,
                },
            )

    transaction = db.transaction()
    append_in_transaction(transaction, doc_ref, message)


if __name__ == "__main__":
    user_id = "test"
    chat_id = "456"
    conversation = [
        {"role": "user", "content": "asdfasdfas"},
        {"role": "assistant", "content": "aasdfs"},
    ]
    add_chat_history(user_id, chat_id, [])
    old_conversation = get_chat_history(user_id, chat_id)
    print(old_conversation)

    print("Message to be added to database: ", conversation)

    append_to_chat_history(user_id, chat_id, conversation)
    conversation = get_chat_history(user_id, chat_id)
    print(conversation)
