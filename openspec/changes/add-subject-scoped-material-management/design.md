## Context

See `proposal.md` for motivation. The Flask application currently authenticates only `teacher` and `student`, keeps one `class_id` on each user, and applies that class scope in material and retrieval services. `Material`, `KnowledgeEntry`, and `KnowledgeChunk` carry class ownership; upload files reside below a class directory. PostgreSQL is the production datastore, with pgvector and pg_trgm already required; SQLite remains the fast unit-test dialect.

## Goals / Non-Goals

**Goals:**

- Enforce a server-derived authorization chain: super administrator → granted class administrator → class subject and assigned teacher → material/retrieval operation.
- Make subject a durable, query-efficient provenance dimension for files, materials, chunks, retrieval hits, and citations.
- Preserve current student access to all materials in the student's class while sharply limiting teacher content access to assigned subjects.
- Migrate current data without changing source text, material IDs, or ready vector values.

**Non-Goals:**

- Course scheduling, timetables, grading, parent access, or a general organization/department tree.
- Cross-class teacher assignments; one teacher may receive multiple subjects only within the teacher's effective class in this change.
- Re-ranking, streaming answers, a new vector database, or exposing embedding data to browsers.
- Bulk file moves performed by a browser or by user-controlled server paths.

## Decisions

### 1. Use explicit role grants instead of role-name convention

Add `super_admin` and `class_admin` to the role set. Add a `class_admin_grants` relation (`admin_user_id`, `class_id`, `created_by`, timestamps, unique admin/class) rather than assuming a class administrator's `users.class_id` is sufficient. Keep a user's existing home `class_id` for compatibility, but resolve administrative class scope from grants. This permits a super administrator to govern class administrators without granting content access.

A `class_subjects` relation will contain `id`, `class_id`, stable generated/public key, display name, normalized name, active/archived state, creator and timestamps. A `teacher_subject_assignments` relation will contain `teacher_id`, `subject_id`, grant metadata and an active state, with a uniqueness constraint per teacher/subject. Assignment requires an existing teacher membership in the subject's class.

Alternative: encode subject names in material paths or add a `subject` string to users and materials. Rejected because renames, multi-subject teachers, auditability, joins, and authorization revocation would be unsafe or ambiguous.

### 2. Separate administrative authority from content authority

`super_admin` manages class administrator accounts and their grants. `class_admin` manages only subjects and teacher-subject assignments in granted classes. Neither administrative role receives implicit material body, file, retrieval, or mutation access from that administrative role alone. A class administrator needing teaching access must also be a teacher with an explicit subject assignment. This least-privilege default directly implements the stated management hierarchy without making a coordinator an unrestricted reader of student/teacher material.

Alternative: make class administrators all-subject material owners. Rejected because it expands content access beyond the stated class-administration responsibility; it can be added later as a deliberate policy change.

### 3. Put `subject_id` on material and retrieval-facing records

Add non-null `subject_id` foreign keys to `materials`, `knowledge_entries`, and `knowledge_chunks`, plus composite indexes beginning with `class_id, subject_id`. `KnowledgeIndexGeneration` inherits ownership through its entry and must be validated against it during build/rebuild. Index creation and chunk replacement copy the material/entry subject atomically. Retrieval's base predicate joins/filters both `class_id` and the authorized subject set before keyword score calculation, pgvector candidate ordering, RRF, and material lookup.

This denormalization makes the critical ready-chunk predicates straightforward and protects against a buggy final lookup. Database migration checks and service validation maintain `material.class_id == subject.class_id` and equivalent entry/chunk provenance.

### 4. Treat request identifiers as narrowing selectors, never authority

Expose role-focused APIs under a new administrative namespace, for example:

- `GET/POST /api/admin/class-admins` and `PUT/DELETE /api/admin/class-admins/<user_id>/classes/<class_id>` for super administrators.
- `GET/POST /api/classes/<class_id>/subjects`, `PUT /api/classes/<class_id>/subjects/<subject_id>`, and assignment routes for authorized class administrators.
- `GET /api/classes/<class_id>/subjects` for members' visible subjects; material APIs accept a subject path or subject filter; upload requires a subject selection.

`class_id` remains a compatibility path value but is resolved to the authenticated effective class for teachers/students. `subject_id` is checked against the server-computed allowed set; unknown, cross-class, or unassigned identifiers return an authorization-safe response without existence disclosure. All mutations retain CSRF protection.

The frontend gains role-aware pages/sections: super administrator governance, class administrator subject/assignment management, a teacher subject selector that enables only assigned-folder mutations, and an all-subject student browser. UI capability flags are convenience only; the API is authoritative.

### 5. Store files in generated class/subject directories and migrate safely

New uploads use `UPLOAD_DIR/<class-id>/<subject-id>/<uuid>.<suffix>` with the existing Unicode display filename kept separately. No route returns this path. File removal reuses a validated storage-root containment check.

Add an idempotent schema/data migration before making `subject_id` non-null: create one archived `历史待归档` subject per existing class, migrate any unmapped material and all derived knowledge rows to it, and leave original file bytes and `body_text` untouched. New files begin using subject directories; existing files need not be physically moved during the database migration because their opaque `storage_path` remains valid. A later controlled maintenance migration may move them after verifying source/destination containment and DB commit semantics.

Alternative: immediately move every existing file as part of the DDL migration. Rejected because a database/file dual-write failure risks orphaning customer files; logical subject assignment first preserves rollback safety.

### 6. Preserve established retrieval and answer protections under the new predicate

The retrieval service receives an authorization context rather than a client class alone: effective class, caller role, allowed subject IDs, and optional narrowed subject. It continues to execute keyword, vector, and hybrid independently as today, with pgvector threshold 0.35 and RRF `k=60`. Hit and citation serializers add `subject_id` and `subject_name`. Answer orchestration still passes only authorized retrieved chunk text plus limited valid history to the server-side chat provider.

## Risks / Trade-offs

- [Existing no-subject data would become inaccessible] → backfill every material/entry/chunk into the per-class historical subject before constraints and authorization become mandatory; prove idempotence in PostgreSQL integration tests.
- [Authorization bugs could leak a same-class but different-subject hit] → centralize allowed-subject resolution, require it in every material/retrieval repository query, and test direct API, keyword, vector, hybrid, final lookup, download, and answer paths.
- [Subject archival could strand materials] → archive instead of delete populated subjects; allow reassignment only through a transactional, auditable administrator workflow.
- [Many assigned subjects create a large SQL `IN` predicate] → use a joined assignment relation/subquery for teacher scope, add composite ready-chunk indexes, and measure PostgreSQL query plans before enabling HNSW tuning changes.
- [Role promotion changes sessions mid-flight] → authorization reads persistent role/grant records on each protected request; revoked grants take effect without trusting stale browser flags.
- [Deployment rollback after writing new records] → run backward-compatible nullable columns and backfill first; delay non-null constraints and UI/API enforcement until validation succeeds. Keep the old class-only storage path readable during rollback.

## Migration Plan

1. Add roles, grants, subjects, teacher assignments, nullable subject references, audit metadata, and PostgreSQL indexes through an idempotent schema migration; update test SQLite schema through the same models.
2. Seed only non-production demonstrative super admin, class administrator, subjects, and assignments from explicit environment configuration; do not introduce published default production credentials.
3. Create per-class historical subjects and backfill material, entry, and chunk subject IDs in bounded transactions; verify counts, class consistency, and absence of orphaned ready chunks.
4. Deploy read-compatible serializers and subject-management APIs; validate authorization, migration checks, and PostgreSQL keyword/vector plans.
5. Require subject selection for new teacher uploads, enable subject-aware material/retrieval predicates, and then enforce non-null/FK constraints once the backfill report is clean.
6. Roll back application code only while old class-only reads remain compatible; do not drop new ownership data. If migration validation fails, stop before enforcement and restore from the database backup rather than deleting file directories.

## Open Questions

None. The agreed policy is that students read all own-class subjects, while administrators manage assignments and do not receive implicit material access.
