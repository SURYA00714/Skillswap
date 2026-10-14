"""
Compatibility layer providing db and bucket interfaces backed by local SQLite / PostgreSQL.
This avoids needing Firebase credentials while preserving collection/document syntax.
"""
import os
import json
import uuid
from datetime import datetime

# Store data in instance/nosql_store.json if file-backed, or memory / /tmp on Vercel
def _get_bundle_path():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "instance", "nosql_store.json"))

def _get_store_path():
    if os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        return "/tmp/nosql_store.json"
    return _get_bundle_path()

STORE_PATH = _get_store_path()

_memory_store = {}

def _load_store():
    global _memory_store
    if _memory_store and _memory_store.get("users"):
        return _memory_store
        
    path = _get_store_path()
    bundle_path = _get_bundle_path()

    # Pre-populate serverless /tmp from bundled seed data if missing
    if path != bundle_path and not os.path.exists(path) and os.path.exists(bundle_path):
        try:
            with open(bundle_path, "r", encoding="utf-8") as bf:
                seed_data = json.load(bf)
                if isinstance(seed_data, dict):
                    _save_store(seed_data)
                    return _memory_store
        except Exception:
            pass

    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict):
                    # Ensure pre-defined users and posts are merged if missing
                    if not data.get("users") and os.path.exists(bundle_path):
                        try:
                            with open(bundle_path, "r", encoding="utf-8") as bf:
                                bundle_data = json.load(bf)
                                for col, items in bundle_data.items():
                                    data.setdefault(col, {}).update(items)
                        except Exception:
                            pass
                    _memory_store = data
                    return _memory_store
        except Exception:
            pass

    # Fallback to bundle directly
    if os.path.exists(bundle_path):
        try:
            with open(bundle_path, "r", encoding="utf-8") as bf:
                data = json.load(bf)
                if isinstance(data, dict):
                    _memory_store = data
                    return _memory_store
        except Exception:
            pass

    return _memory_store

def _save_store(data):
    global _memory_store
    _memory_store = data
    path = _get_store_path()
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, default=str, indent=2)
    except Exception:
        pass

class DocumentSnapshot:
    def __init__(self, doc_id, data):
        self.id = doc_id
        self._data = data or {}
        self.exists = data is not None

    def to_dict(self):
        return dict(self._data) if self._data else {}

    def get(self, field, default=None):
        return self._data.get(field, default)

class DocumentReference:
    def __init__(self, collection_name, doc_id):
        self.collection_name = collection_name
        self.id = doc_id or str(uuid.uuid4())

    def get(self):
        store = _load_store()
        col = store.get(self.collection_name, {})
        data = col.get(self.id)
        return DocumentSnapshot(self.id, data)

    def set(self, data, merge=False):
        store = _load_store()
        col = store.setdefault(self.collection_name, {})
        clean_data = dict(data)
        # handle special server timestamps
        for k, v in clean_data.items():
            if str(v) == "SERVER_TIMESTAMP":
                clean_data[k] = datetime.utcnow().isoformat()
        if merge and self.id in col:
            col[self.id].update(clean_data)
        else:
            col[self.id] = clean_data
        _save_store(store)
        return self

    def update(self, data):
        return self.set(data, merge=True)

    def delete(self):
        store = _load_store()
        col = store.setdefault(self.collection_name, {})
        if self.id in col:
            del col[self.id]
            _save_store(store)

class Query:
    def __init__(self, collection_name, filters=None, limit_val=None, order_by_field=None, descending=False):
        self.collection_name = collection_name
        self.filters = filters or []
        self.limit_val = limit_val
        self.order_by_field = order_by_field
        self.descending = descending

    def where(self, field, op, val):
        new_filters = list(self.filters)
        new_filters.append((field, op, val))
        return Query(self.collection_name, new_filters, self.limit_val, self.order_by_field, self.descending)

    def order_by(self, field, direction="ASCENDING"):
        desc = direction.upper().endswith("DESCENDING") or direction.upper() == "DESC"
        return Query(self.collection_name, self.filters, self.limit_val, field, desc)

    def limit(self, val):
        return Query(self.collection_name, self.filters, val, self.order_by_field, self.descending)

    def stream(self):
        store = _load_store()
        col = store.get(self.collection_name, {})
        results = []
        for doc_id, data in col.items():
            match = True
            for field, op, val in self.filters:
                actual = data.get(field)
                if op == "==":
                    if actual != val:
                        match = False
                        break
                elif op == "!=":
                    if actual == val:
                        match = False
                        break
                elif op == "array_contains":
                    if not isinstance(actual, (list, tuple)) or val not in actual:
                        match = False
                        break
                elif op == "in":
                    if actual not in val:
                        match = False
                        break
            if match:
                results.append(DocumentSnapshot(doc_id, data))

        if self.order_by_field:
            results.sort(key=lambda s: str(s.get(self.order_by_field, "")), reverse=self.descending)

        if self.limit_val is not None:
            results = results[:self.limit_val]

        return results

    def get(self):
        return self.stream()

class CollectionReference:
    def __init__(self, name):
        self.name = name

    def document(self, doc_id=None):
        return DocumentReference(self.name, doc_id)

    def where(self, field, op, val):
        return Query(self.name, [(field, op, val)])

    def order_by(self, field, direction="ASCENDING"):
        return Query(self.name, order_by_field=field, descending=direction.upper().startswith("DESC"))

    def limit(self, val):
        return Query(self.name, limit_val=val)

    def stream(self):
        return Query(self.name).stream()

    def get(self):
        return self.stream()

class Batch:
    def __init__(self):
        self.operations = []

    @property
    def _write_pbs(self):
        return self.operations

    def set(self, doc_ref, data, merge=False):
        self.operations.append(('set', doc_ref, data, merge))

    def update(self, doc_ref, data):
        self.operations.append(('update', doc_ref, data, True))

    def delete(self, doc_ref):
        self.operations.append(('delete', doc_ref))

    def commit(self):
        for op in self.operations:
            if op[0] in ('set', 'update'):
                op[1].set(op[2], merge=op[3])
            elif op[0] == 'delete':
                op[1].delete()
        self.operations.clear()

class FirestoreClient:
    SERVER_TIMESTAMP = "SERVER_TIMESTAMP"

    def collection(self, name):
        return CollectionReference(name)

    def batch(self):
        return Batch()

class FakeStorageBucket:
    def blob(self, name):
        class FakeBlob:
            def upload_from_file(self, *args, **kwargs): pass
            def upload_from_string(self, *args, **kwargs): pass
            def make_public(self): pass
            public_url = ""
        return FakeBlob()

# Export db, bucket, firestore compatibility
db = FirestoreClient()
bucket = FakeStorageBucket()
firestore = FirestoreClient
