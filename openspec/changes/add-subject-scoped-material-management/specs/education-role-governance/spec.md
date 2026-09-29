## Purpose

为教务处、班主任、任课教师和学生建立可审计的授权层级，使班级学科与任课教师关系只能由恰当的上级角色维护。

## ADDED Requirements

### Requirement: The system distinguishes education administration roles
The system SHALL distinguish `super_admin` (教务处), `class_admin` (班主任), `teacher`, and `student` identities in authenticated responses and server-side authorization. A role SHALL not acquire another role's administrative or material privilege merely because it shares a class with that role.

#### Scenario: Authenticated identity reports its administrative role
- **WHEN** a super administrator or class administrator signs in successfully
- **THEN** the authenticated identity identifies that role without exposing another user's session, password, or authorization records

#### Scenario: A teacher attempts an administrative operation
- **WHEN** a teacher directly invokes an endpoint reserved for super administrators or class administrators
- **THEN** the system returns HTTP 403 and creates, changes, or deletes no administrative record

### Requirement: Super administrators manage class administrator scope
The system SHALL allow only a super administrator to create, activate, deactivate, and assign class administrator accounts. A class-administrator-to-class grant SHALL be explicit and auditable; removing a grant SHALL immediately prevent that administrator from managing that class.

#### Scenario: Super administrator assigns a class administrator
- **WHEN** a super administrator grants a class administrator authority for a selected class
- **THEN** the administrator can manage subject and teacher assignments only in that granted class

#### Scenario: Class administrator attempts to grant another class
- **WHEN** a class administrator attempts to create or alter class-administrator scope
- **THEN** the system returns HTTP 403 and does not reveal whether the target administrator or class exists outside the caller's authorized scope

### Requirement: Class administrators manage subject and teacher assignments only within granted classes
The system SHALL allow a class administrator to create, rename, activate, archive, and inspect subjects for a granted class and to grant or revoke a teacher's assignment to those subjects. The system SHALL verify both the class grant and the teacher's membership before persisting an assignment.

#### Scenario: Class administrator assigns a class teacher to mathematics
- **WHEN** a class administrator for class A assigns an active class-A teacher to class A's mathematics subject
- **THEN** the assignment becomes available for server-side material and retrieval authorization

#### Scenario: Class administrator targets another class
- **WHEN** a class-A administrator submits a subject or teacher assignment request naming class B
- **THEN** the system rejects it without creating or disclosing class-B subject or assignment data

### Requirement: Administrative changes preserve safe access transitions
The system SHALL refuse to delete a subject that still owns materials and SHALL require archival or reassignment through an authorized workflow. Revoking a teacher-subject assignment SHALL remove that teacher's material-management and retrieval access to the subject without deleting its materials, chunks, vectors, or student access.

#### Scenario: Administrator revokes an assigned teacher
- **WHEN** a class administrator revokes a teacher's assignment to a subject
- **THEN** later teacher requests for that subject are denied while same-class students can continue reading and retrieving its ready materials

#### Scenario: Administrator attempts to delete a populated subject
- **WHEN** a class administrator attempts to delete a subject that contains one or more materials
- **THEN** the system returns a conflict response and retains the subject and all associated data
