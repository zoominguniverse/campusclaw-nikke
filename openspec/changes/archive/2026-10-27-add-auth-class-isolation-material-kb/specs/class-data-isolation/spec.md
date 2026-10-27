## Purpose

将班级定义为 CampusClaw 的服务端数据边界，确保认证用户只能访问其授权班级的数据，尤其防止通过直接构造请求绕过前端界面限制。

## ADDED Requirements

### Requirement: Class-scoped material authorization

The system SHALL derive the caller's permitted class scope from the authenticated server-side identity and SHALL enforce that scope on all material and knowledge-base reads, lists, and writes. Every repository query that can return class-owned data SHALL apply the server-derived `class_id` predicate before returning records.

#### Scenario: User reads material from their own class

- **WHEN** an authenticated user requests a material belonging to their authorized class
- **THEN** the system permits the read when the user's role otherwise allows it

#### Scenario: User reads material from another class

- **WHEN** an authenticated user requests a material belonging to a class outside the user's authorized scope
- **THEN** the system returns the same HTTP 404 response used for an absent material and does not disclose the material title, body, knowledge-base content, upload path, or storage key

### Requirement: Server-side class isolation

The system SHALL enforce class isolation at the server-side authorization and data-query boundary and SHALL NOT rely on hidden buttons, client-side filtering, or a client-supplied class identifier as the security control.

#### Scenario: Client changes a class identifier

- **WHEN** a user changes a class identifier in a URL, query, form, or request body to target another class
- **THEN** the server discards that client value, recomputes scope from the authenticated identity, and operates only on the caller's server-derived class

#### Scenario: Client omits or falsifies class context

- **WHEN** a protected material request omits or falsifies its class context
- **THEN** the server does not infer authorization from that client value and rejects or resolves the request only according to the authenticated user's server-side scope

### Requirement: Class-scoped material listing

The system SHALL return material list results limited to the requesting user's authorized class scope.

#### Scenario: User lists materials

- **WHEN** an authenticated user requests the material list for their class
- **THEN** every returned record belongs to an authorized class and no record from another class is included

#### Scenario: User attempts to list another class

- **WHEN** an authenticated user requests a material list for a class outside the user's authorized scope
- **THEN** the system returns only records from the caller's server-derived class and no record from the client-requested class is exposed

#### Scenario: List filters cannot enumerate another class

- **WHEN** an authenticated class-A user uses pagination, search, sorting, or an altered list parameter while listing materials
- **THEN** every result and result count remains limited to class A and cannot reveal the seeded distinguishable B-class material title

#### Scenario: Cross-class mutation is rejected

- **WHEN** an authenticated user attempts to update, replace, or delete a material or knowledge-base record owned by another class
- **THEN** the server cannot resolve that record inside the caller's derived class scope, leaves the other class's record unchanged, and returns no cross-class record content
