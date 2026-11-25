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
    app_dir = os.path.dirname(__file__)
    internal_path = os.path.abspath(os.path.join(app_dir, "nosql_store.json"))
    if os.path.exists(internal_path):
        return internal_path
    return os.path.abspath(os.path.join(app_dir, "..", "instance", "nosql_store.json"))

def _get_store_path():
    if os.environ.get("VERCEL") or os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
        return "/tmp/nosql_store.json"
    return _get_bundle_path()

STORE_PATH = _get_store_path()

_memory_store = {}

def _get_pg_connection():
    # Supports DATABASE_URL (standard) and POSTGRES_URL (Vercel Storage Neon integration)
    db_url = (
        os.environ.get("DATABASE_URL")
        or os.environ.get("POSTGRES_URL")
        or os.environ.get("POSTGRES_URL_NON_POOLING")
        or os.environ.get("POSTGRES_PRISMA_URL")
    )
    if not db_url:
        return None
    db_url = db_url.replace("&channel_binding=require", "").replace("channel_binding=require&", "").replace("?channel_binding=require", "")
    
    # 2 retry attempts with 10s timeout to allow Neon serverless compute to wake from sleep
    for attempt in range(2):
        try:
            import psycopg2
            conn = psycopg2.connect(db_url, connect_timeout=10)
            conn.autocommit = True
            return conn
        except Exception as e:
            try:
                import psycopg
                conn = psycopg.connect(db_url, connect_timeout=10, autocommit=True)
                return conn
            except Exception:
                pass
    return None

def _load_store():
    global _memory_store

    # 1. Primary: Attempt to fetch latest shared store from PostgreSQL
    try:
        conn = _get_pg_connection()
        if conn:
            with conn.cursor() as cur:
                cur.execute("CREATE TABLE IF NOT EXISTS nosql_kv_store (key TEXT PRIMARY KEY, value TEXT);")
                cur.execute("SELECT value FROM nosql_kv_store WHERE key = 'store';")
                row = cur.fetchone()
                if row and row[0]:
                    pg_data = json.loads(row[0])
                    if isinstance(pg_data, dict) and pg_data.get("users"):
                        _memory_store = pg_data
                        conn.close()
                        # Cache to local /tmp path so serverless container reads fast
                        try:
                            path = _get_store_path()
                            os.makedirs(os.path.dirname(path), exist_ok=True)
                            with open(path, "w", encoding="utf-8") as f:
                                json.dump(_memory_store, f, default=str)
                        except Exception:
                            pass
                        return _memory_store
            conn.close()
    except Exception as e:
        print(f"⚠️ Notice: Cloud PostgreSQL fetch error: {e}")

    # 2. In-memory check
    if _memory_store and _memory_store.get("users"):
        return _memory_store
        
    path = _get_store_path()
    bundle_path = _get_bundle_path()

    # 3. Read cached file from disk if present
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, dict) and data.get("users"):
                    _memory_store = data
                    return _memory_store
        except Exception:
            pass

    # 4. Fallback to bundle seed data ONLY if store has never been populated
    if os.path.exists(bundle_path):
        try:
            with open(bundle_path, "r", encoding="utf-8") as bf:
                data = json.load(bf)
                if isinstance(data, dict):
                    _memory_store = data
                    # Only seed to remote PostgreSQL if table was completely empty
                    try:
                        conn = _get_pg_connection()
                        if conn:
                            with conn.cursor() as cur:
                                cur.execute("SELECT count(*) FROM nosql_kv_store WHERE key = 'store';")
                                if cur.fetchone()[0] == 0:
                                    cur.execute(
                                        "INSERT INTO nosql_kv_store (key, value) VALUES ('store', %s) ON CONFLICT DO NOTHING;",
                                        (json.dumps(data, default=str),)
                                    )
                            conn.close()
                    except Exception:
                        pass
                    return _memory_store
        except Exception:
            pass

    return _memory_store

def _save_store(data):
    global _memory_store
    _memory_store = data
    path = _get_store_path()
    
    # 1. Save to local filesystem
    try:
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, default=str, indent=2)
    except Exception:
        pass

    # 2. Persist to shared PostgreSQL for cross-container serverless synchronization
    try:
        conn = _get_pg_connection()
        if conn:
            with conn.cursor() as cur:
                cur.execute("CREATE TABLE IF NOT EXISTS nosql_kv_store (key TEXT PRIMARY KEY, value TEXT);")
                json_str = json.dumps(data, default=str)
                cur.execute("""
                    INSERT INTO nosql_kv_store (key, value) VALUES ('store', %s)
                    ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value;
                """, (json_str,))
            conn.close()
    except Exception:
        pass

def _sync_to_relational_table(collection_name, doc_id, data):
    """
    Mirror NoSQL document updates directly into Neon PostgreSQL relational tables
    so that Vercel Storage / Neon Console table viewer shows live rows.
    """
    try:
        conn = _get_pg_connection()
        if not conn:
            return
        with conn.cursor() as cur:
            if collection_name == 'users':
                cur.execute('''
                    INSERT INTO users (
                        "id", "fullName", "email", "title", "bio", "city", "state", "location",
                        "profilePhotoUrl", "profileVisibility", "offeredSkills", "wantedSkills",
                        "rating", "reviewCount", "onboarding_completed"
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT ("id") DO UPDATE SET
                        "fullName" = COALESCE(EXCLUDED."fullName", users."fullName"),
                        "email" = COALESCE(EXCLUDED."email", users."email"),
                        "title" = COALESCE(EXCLUDED."title", users."title"),
                        "bio" = COALESCE(EXCLUDED."bio", users."bio"),
                        "city" = COALESCE(EXCLUDED."city", users."city"),
                        "state" = COALESCE(EXCLUDED."state", users."state"),
                        "location" = COALESCE(EXCLUDED."location", users."location"),
                        "profilePhotoUrl" = COALESCE(EXCLUDED."profilePhotoUrl", users."profilePhotoUrl"),
                        "profileVisibility" = COALESCE(EXCLUDED."profileVisibility", users."profileVisibility"),
                        "offeredSkills" = COALESCE(EXCLUDED."offeredSkills", users."offeredSkills"),
                        "wantedSkills" = COALESCE(EXCLUDED."wantedSkills", users."wantedSkills"),
                        "rating" = COALESCE(EXCLUDED."rating", users."rating"),
                        "reviewCount" = COALESCE(EXCLUDED."reviewCount", users."reviewCount"),
                        "onboarding_completed" = COALESCE(EXCLUDED."onboarding_completed", users."onboarding_completed");
                ''', (
                    doc_id,
                    data.get('fullName') or data.get('name'),
                    data.get('email', ''),
                    data.get('title') or data.get('headline'),
                    data.get('bio') or data.get('about'),
                    data.get('city'),
                    data.get('state'),
                    data.get('location'),
                    data.get('photo_url') or data.get('profilePhotoUrl'),
                    data.get('profileVisibility', 'Public'),
                    json.dumps(data.get('offeredSkill') or data.get('offeredSkills') or []),
                    json.dumps(data.get('requestedSkill') or data.get('wantedSkill') or data.get('wantedSkills') or []),
                    float(data.get('rating', 5.0)),
                    int(data.get('review_count') or data.get('reviewCount') or 0),
                    bool(data.get('onboarding_completed', False))
                ))
            elif collection_name == 'library_resources':
                cur.execute('''
                    INSERT INTO library_resources (
                        "id", "uploaderId", "title", "description", "category",
                        "skillTag", "resourceType", "fileUrl", "fileName", "fileSizeBytes"
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT ("id") DO UPDATE SET
                        "title" = EXCLUDED."title",
                        "description" = EXCLUDED."description",
                        "category" = EXCLUDED."category",
                        "skillTag" = EXCLUDED."skillTag",
                        "fileUrl" = EXCLUDED."fileUrl",
                        "fileName" = EXCLUDED."fileName",
                        "fileSizeBytes" = EXCLUDED."fileSizeBytes";
                ''', (
                    doc_id,
                    data.get('uploaderId', 'unknown'),
                    data.get('title', 'Untitled'),
                    data.get('description', ''),
                    data.get('category', 'General'),
                    data.get('skillTag', ''),
                    data.get('resourceType', 'file'),
                    data.get('fileUrl', ''),
                    data.get('fileName', ''),
                    int(data.get('fileSizeBytes', 0))
                ))
            elif collection_name == 'swaps':
                cur.execute('''
                    INSERT INTO swaps (
                        "id", "swapId", "fromUserId", "toUserId", "offeredSkill", "requestedSkill", "message", "status"
                    ) VALUES (
                        %s, %s, %s, %s, %s, %s, %s, %s
                    )
                    ON CONFLICT ("id") DO UPDATE SET
                        "status" = EXCLUDED."status",
                        "message" = EXCLUDED."message";
                ''', (
                    doc_id,
                    data.get('swapId') or doc_id,
                    data.get('fromUserId', ''),
                    data.get('toUserId', ''),
                    data.get('offeredSkill', ''),
                    data.get('requestedSkill', ''),
                    data.get('message', ''),
                    data.get('status', 'pending')
                ))
        conn.close()
    except Exception as e:
        print(f"⚠️ Relational sync notice ({collection_name}): {e}")

class ArrayUnion:
    def __init__(self, values):
        self.values = list(values) if isinstance(values, (list, tuple)) else [values]

class Increment:
    def __init__(self, amount):
        self.amount = amount

class DocumentSnapshot:
    def __init__(self, doc_id, data, collection_name=None):
        self.id = doc_id
        self._data = data or {}
        self.exists = data is not None
        self.collection_name = collection_name
        self._reference = DocumentReference(collection_name, doc_id) if collection_name else None

    @property
    def reference(self):
        if self._reference is not None:
            return self._reference
        if self.collection_name:
            self._reference = DocumentReference(self.collection_name, self.id)
            return self._reference
        return DocumentReference('swaps', self.id)

    @reference.setter
    def reference(self, val):
        self._reference = val

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
        return DocumentSnapshot(self.id, data, collection_name=self.collection_name)

    def set(self, data, merge=False):
        store = _load_store()
        col = store.setdefault(self.collection_name, {})
        target = dict(col.get(self.id, {})) if merge and self.id in col else {}
        
        clean_data = dict(data)
        for k, v in clean_data.items():
            if str(v) == "SERVER_TIMESTAMP" or v == "SERVER_TIMESTAMP":
                target[k] = datetime.utcnow().isoformat()
            elif isinstance(v, ArrayUnion):
                existing_list = target.get(k, [])
                if not isinstance(existing_list, list):
                    existing_list = []
                for val in v.values:
                    if val not in existing_list:
                        existing_list.append(val)
                target[k] = existing_list
            elif isinstance(v, Increment):
                existing_val = target.get(k, 0)
                try:
                    target[k] = (existing_val or 0) + v.amount
                except Exception:
                    target[k] = v.amount
            else:
                target[k] = v
                
        col[self.id] = target
        _save_store(store)
        _sync_to_relational_table(self.collection_name, self.id, target)
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
    ASCENDING = "ASCENDING"
    DESCENDING = "DESCENDING"

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
                results.append(DocumentSnapshot(doc_id, data, collection_name=self.collection_name))

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

    def add(self, data):
        doc_ref = self.document()
        doc_ref.set(data)
        return (None, doc_ref)

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
    ArrayUnion = ArrayUnion
    Increment = Increment
    Query = Query

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
