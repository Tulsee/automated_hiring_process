/**
 * Roles, permissions and administration users.
 *
 * This is where the superadmin (or anyone granted `roles:manage` /
 * `users:manage`) builds the access model the request asks for: create a role,
 * tick the permissions it grants, then create users and assign them a role.
 *
 * The page shows only the sections the viewer may use, and the server enforces
 * the same — a viewer reaching the URL directly still gets 403 from the API.
 */

import { useState } from "react";
import { api } from "../api/client";
import { useApi, useAction } from "../hooks/useApi";
import { useAuth } from "../auth/context";
import { Icon } from "../components/Icon";
import {
  EmptyState,
  ErrorState,
  Loading,
  Modal,
  Notice,
  Panel,
  StatusPill,
} from "../components/primitives";
import { PageHeader } from "../components/AppShell";
import type { PermissionInfo, Role } from "../types";

export function AccessControlPage() {
  const { can } = useAuth();

  const canRoles = can("roles:manage");
  const canUsers = can("users:manage");

  return (
    <>
      <PageHeader
        eyebrow="ADMINISTRATION"
        title="Access"
        highlight="control"
        subtitle="Define what roles can do, then assign them to the hiring team."
      />

      {!canRoles && !canUsers ? (
        <Panel>
          <Notice icon="alert" title="Nothing to manage here">
            Managing roles and users needs the roles:manage or users:manage
            permission, which only the superadmin holds by default.
          </Notice>
        </Panel>
      ) : null}

      {canRoles ? <RolesSection /> : null}
      {canUsers ? <UsersSection canRoles={canRoles} /> : null}
    </>
  );
}

/* ----------------------------------------------------------------- roles */

function RolesSection() {
  const roles = useApi(() => api.listRoles(), []);
  const permissions = useApi(() => api.listPermissions(), []);
  const [editing, setEditing] = useState<Role | "new" | null>(null);

  return (
    <Panel
      title="Roles"
      subtitle="A role is a named set of permissions"
      action={
        <button
          type="button"
          className="button button--primary"
          onClick={() => setEditing("new")}
        >
          <Icon name="plus" size={13} /> New role
        </button>
      }
    >
      {roles.error ? (
        <ErrorState error={roles.error} onRetry={roles.reload} />
      ) : roles.loading ? (
        <Loading what="roles" />
      ) : roles.data!.length === 0 ? (
        <EmptyState title="No roles yet">
          Create one to start granting the hiring team access.
        </EmptyState>
      ) : (
        <div className="table-scroll">
          <table>
            <caption className="sr-only">Roles and their permissions</caption>
            <thead>
              <tr>
                <th scope="col">Role</th>
                <th scope="col">Permissions</th>
                <th scope="col" />
              </tr>
            </thead>
            <tbody>
              {roles.data!.map((role) => (
                <tr key={role.id}>
                  <td>
                    <strong>{role.name}</strong>
                    <span className="table-subtext">{role.description}</span>
                  </td>
                  <td>
                    {role.permissions.length === 0 ? (
                      <span className="muted">none</span>
                    ) : (
                      <span className="skill-list" style={{ display: "flex" }}>
                        {role.permissions.map((permission) => (
                          <span key={permission} className="skill-chip">
                            {permission}
                          </span>
                        ))}
                      </span>
                    )}
                  </td>
                  <td>
                    <button
                      type="button"
                      className="text-button"
                      aria-label={`Edit ${role.name}`}
                      onClick={() => setEditing(role)}
                    >
                      Edit
                    </button>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}

      {editing ? (
        <RoleModal
          role={editing === "new" ? null : editing}
          permissions={permissions.data?.permissions ?? []}
          onClose={() => setEditing(null)}
          onSaved={() => {
            setEditing(null);
            roles.reload();
          }}
        />
      ) : null}
    </Panel>
  );
}

function RoleModal({
  role,
  permissions,
  onClose,
  onSaved,
}: {
  role: Role | null;
  permissions: PermissionInfo[];
  onClose: () => void;
  onSaved: () => void;
}) {
  const [name, setName] = useState(role?.name ?? "");
  const [description, setDescription] = useState(role?.description ?? "");
  const [granted, setGranted] = useState<Set<string>>(
    new Set(role?.permissions ?? []),
  );

  const create = useAction(api.createRole);
  const update = useAction(api.updateRole);
  const remove = useAction(api.deleteRole);
  const pending = create.pending || update.pending || remove.pending;
  const error = create.error ?? update.error ?? remove.error;

  function toggle(permission: string) {
    setGranted((current) => {
      const next = new Set(current);
      if (next.has(permission)) next.delete(permission);
      else next.add(permission);
      return next;
    });
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();

    const permissionList = [...granted];

    const result = role
      ? await update.run(role.name, {
          description,
          permissions: permissionList,
        })
      : await create.run({ name: name.trim(), description, permissions: permissionList });

    if (result) onSaved();
  }

  return (
    <Modal title={role ? `Edit role: ${role.name}` : "New role"} onClose={onClose}>
      <form className="form-stack" onSubmit={submit}>
        {role ? null : (
          <label>
            Role name
            <input
              value={name}
              onChange={(event) => setName(event.target.value)}
              placeholder="interviewer"
              required
            />
          </label>
        )}

        <label>
          Description
          <input
            value={description}
            onChange={(event) => setDescription(event.target.value)}
            placeholder="What this role is for"
          />
        </label>

        <fieldset className="question-editor">
          <legend>Permissions this role grants</legend>
          {permissions.map((permission) => (
            <label key={permission.name} className="permission-row">
              <input
                type="checkbox"
                checked={granted.has(permission.name)}
                onChange={() => toggle(permission.name)}
              />
              <span>
                <strong>{permission.name}</strong>
                <small>{permission.description}</small>
              </span>
            </label>
          ))}
        </fieldset>

        {error ? (
          <Notice icon="alert" title="Could not save">
            {error.message}
          </Notice>
        ) : null}

        <div className="modal-actions">
          {role ? (
            <button
              type="button"
              className="button button--secondary"
              style={{ marginRight: "auto", color: "var(--amber-ink)" }}
              disabled={pending}
              onClick={async () => {
                const done = await remove.run(role.name);
                if (done) onSaved();
              }}
            >
              {remove.pending ? "Deleting…" : "Delete role"}
            </button>
          ) : null}
          <button type="button" className="button button--secondary" onClick={onClose}>
            Cancel
          </button>
          <button
            type="submit"
            className="button button--primary"
            disabled={pending || (!role && name.trim().length === 0)}
          >
            {pending ? "Saving…" : role ? "Save role" : "Create role"}
          </button>
        </div>
      </form>
    </Modal>
  );
}

/* ----------------------------------------------------------------- users */

function UsersSection({ canRoles }: { canRoles: boolean }) {
  const users = useApi(() => api.listUsers(), []);
  const roles = useApi(() => (canRoles ? api.listRoles() : api.listRoles()), []);
  const [creating, setCreating] = useState(false);

  return (
    <Panel
      title="Administration users"
      subtitle="People on the hiring team, each assigned a role"
      className="access-users"
      action={
        <button
          type="button"
          className="button button--primary"
          onClick={() => setCreating(true)}
        >
          <Icon name="plus" size={13} /> New user
        </button>
      }
    >
      {users.error ? (
        <ErrorState error={users.error} onRetry={users.reload} />
      ) : users.loading ? (
        <Loading what="users" />
      ) : (
        <div className="table-scroll">
          <table>
            <caption className="sr-only">Users and their roles</caption>
            <thead>
              <tr>
                <th scope="col">User</th>
                <th scope="col">Kind</th>
                <th scope="col">Role</th>
                <th scope="col">Status</th>
                <th scope="col" />
              </tr>
            </thead>
            <tbody>
              {users.data!.map((user) => (
                <UserRow
                  key={user.id}
                  user={user}
                  roleNames={(roles.data ?? []).map((role) => role.name)}
                  onChanged={users.reload}
                />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {creating ? (
        <CreateUserModal
          roleNames={(roles.data ?? []).map((role) => role.name)}
          onClose={() => setCreating(false)}
          onCreated={() => {
            setCreating(false);
            users.reload();
          }}
        />
      ) : null}
    </Panel>
  );
}

function UserRow({
  user,
  roleNames,
  onChanged,
}: {
  user: import("../types").AuthUser;
  roleNames: string[];
  onChanged: () => void;
}) {
  const update = useAction(api.updateUser);

  return (
    <tr>
      <td>
        <strong>{user.name}</strong>
        <span className="table-subtext">{user.email}</span>
      </td>
      <td>
        {user.is_superadmin ? (
          <span className="status status--interview">superadmin</span>
        ) : (
          user.kind
        )}
      </td>
      <td>
        {user.is_superadmin ? (
          <span className="muted">all</span>
        ) : user.kind === "candidate" ? (
          <span className="muted">—</span>
        ) : (
          <select
            value={user.role ?? ""}
            aria-label={`Role for ${user.name}`}
            onChange={async (event) => {
              const done = await update.run(user.id, {
                role: event.target.value || null,
              });
              if (done) onChanged();
            }}
          >
            <option value="">no role</option>
            {roleNames.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        )}
      </td>
      <td>
        <StatusPill value={user.active ? "published" : "draft"} />
      </td>
      <td>
        {user.is_superadmin ? null : (
          <button
            type="button"
            className="text-button"
            disabled={update.pending}
            onClick={async () => {
              const done = await update.run(user.id, { active: !user.active });
              if (done) onChanged();
            }}
          >
            {user.active ? "Disable" : "Enable"}
          </button>
        )}
      </td>
    </tr>
  );
}

function CreateUserModal({
  roleNames,
  onClose,
  onCreated,
}: {
  roleNames: string[];
  onClose: () => void;
  onCreated: () => void;
}) {
  const [email, setEmail] = useState("");
  const [name, setName] = useState("");
  const [password, setPassword] = useState("");
  const [role, setRole] = useState("");

  const create = useAction(api.createAdminUser);

  async function submit(event: React.FormEvent) {
    event.preventDefault();

    const result = await create.run({
      email: email.trim(),
      name: name.trim(),
      password,
      role: role || null,
      kind: "administration",
    });

    if (result) onCreated();
  }

  return (
    <Modal title="New administration user" onClose={onClose}>
      <form className="form-stack" onSubmit={submit}>
        <label>
          Full name
          <input value={name} onChange={(e) => setName(e.target.value)} required />
        </label>
        <label>
          Email
          <input
            type="email"
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
          />
        </label>
        <label>
          Temporary password
          <input
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            minLength={8}
            required
          />
          <span className="privacy-note">
            At least 8 characters. Share it securely; they can change it later.
          </span>
        </label>
        <label>
          Role
          <select value={role} onChange={(e) => setRole(e.target.value)}>
            <option value="">no role (no permissions yet)</option>
            {roleNames.map((name) => (
              <option key={name} value={name}>
                {name}
              </option>
            ))}
          </select>
        </label>

        {create.error ? (
          <Notice icon="alert" title="Could not create user">
            {create.error.message}
          </Notice>
        ) : null}

        <div className="modal-actions">
          <button type="button" className="button button--secondary" onClick={onClose}>
            Cancel
          </button>
          <button
            type="submit"
            className="button button--primary"
            disabled={create.pending}
          >
            {create.pending ? "Creating…" : "Create user"}
          </button>
        </div>
      </form>
    </Modal>
  );
}
