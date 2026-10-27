# material-deletion-ui Specification

## Purpose

Give teachers a deliberate browser control for removing obsolete in-class teaching materials while preserving existing class isolation and deletion safeguards.

## Requirements

### Requirement: Teachers can delete listed materials from the browser
The materials page SHALL display a delete action only for materials in an authenticated teacher's active assigned subjects. The action SHALL require explicit confirmation and use the class-and-subject-scoped deletion API with `Authorization: Bearer <access-token>`, without Cookie authentication or a CSRF-token requirement.

#### Scenario: Teacher confirms deletion
- **WHEN** a teacher confirms deletion for a listed in-class material
- **THEN** the material is removed and the browser refreshes the list without displaying its title, source, or storage path afterward

#### Scenario: Teacher cancels deletion
- **WHEN** a teacher dismisses the confirmation prompt
- **THEN** the browser sends no deletion request and the material remains listed

### Requirement: Students cannot initiate material deletion from the page
The materials page SHALL not render a material-deletion control for student users.

#### Scenario: Student views materials
- **WHEN** a student opens the protected materials page
- **THEN** listed materials provide preview and download controls but no delete action

### Requirement: Deletion feedback is actionable and safe
The materials page SHALL display a text-only success message after deletion and a text-only API error message or generic fallback when deletion fails.

#### Scenario: Deletion fails
- **WHEN** the deletion request returns an error response
- **THEN** the material remains in the browser list and the page displays the failure without inserting response content as HTML
