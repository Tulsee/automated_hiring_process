/**
 * The signed-in user's own profile.
 *
 * A candidate edits their details and the change is live at once. An
 * administration user's edit is not applied directly — it is submitted for a
 * superadmin to approve — so the page says so, and shows when a change of
 * theirs is already pending. Everyone can change their own password
 * immediately; that never needs approval.
 */

import { useRef, useState } from "react";
import { api } from "../api/client";
import { useAuth } from "../auth/context";
import { useAction } from "../hooks/useApi";
import { Icon } from "../components/Icon";
import { Avatar, Notice, Panel } from "../components/primitives";
import { PageHeader } from "../components/AppShell";
import type { ProfileUpdate } from "../types";

export function ProfilePage() {
  const { user, isAdministration, isSuperadmin, refresh } = useAuth();

  if (!user) return null;

  // The superadmin edits directly; other administration users go through
  // approval; candidates edit their own details freely.
  const needsApproval = isAdministration && !isSuperadmin;

  return (
    <>
      <PageHeader
        eyebrow="ACCOUNT"
        title="Your"
        highlight="profile"
        subtitle={
          needsApproval
            ? "Changes to your details are reviewed by a superadmin before they go live."
            : "Update your details and photo."
        }
      />

      {user.has_pending_changes ? (
        <Notice icon="clock" title="A change is awaiting approval">
          You have a profile change pending a superadmin's review. You can keep
          editing; a new submission replaces nothing until it is approved.
        </Notice>
      ) : null}

      <ProfileForm needsApproval={needsApproval} onSaved={refresh} />

      <PasswordForm />
    </>
  );
}

function ProfileForm({
  needsApproval,
  onSaved,
}: {
  needsApproval: boolean;
  onSaved: () => Promise<void>;
}) {
  const { user } = useAuth();
  const profile = user!.profile;

  const [name, setName] = useState(user!.name);
  const [email, setEmail] = useState(user!.email);
  const [phone, setPhone] = useState(profile.phone ?? "");
  const [location, setLocation] = useState(profile.location ?? "");
  const [headline, setHeadline] = useState(profile.headline ?? "");
  const [bio, setBio] = useState(profile.bio ?? "");
  const [photo, setPhoto] = useState<string | null>(profile.photo);
  const [status, setStatus] = useState<"applied" | "pending" | null>(null);
  const [photoError, setPhotoError] = useState<string | null>(null);

  const fileRef = useRef<HTMLInputElement>(null);
  const save = useAction(api.updateMyProfile);

  function onPhoto(event: React.ChangeEvent<HTMLInputElement>) {
    const file = event.target.files?.[0];
    if (!file) return;

    // Base64 inflates ~33%; keep the source small so the user document stays
    // reasonable.
    if (file.size > 512 * 1024) {
      setPhotoError("Please choose an image under 512 KB.");
      return;
    }

    setPhotoError(null);
    const reader = new FileReader();
    reader.onload = () => setPhoto(reader.result as string);
    reader.readAsDataURL(file);
  }

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setStatus(null);

    const changes: ProfileUpdate = {
      name: name.trim(),
      email: email.trim(),
      phone,
      location,
      headline,
      bio,
      photo,
    };

    const result = await save.run(changes);
    if (!result) return;

    setStatus(result.status);
    if (result.status === "applied") await onSaved();
  }

  return (
    <Panel title="Details">
      <form className="form-stack profile-form" onSubmit={submit}>
        <div className="profile-photo-row">
          <Avatar name={name} src={photo} variant="profile" />
          <div>
            <button
              type="button"
              className="button button--secondary"
              onClick={() => fileRef.current?.click()}
            >
              <Icon name="upload" size={13} /> Upload photo
            </button>
            {photo ? (
              <button
                type="button"
                className="text-button"
                onClick={() => setPhoto(null)}
              >
                Remove
              </button>
            ) : null}
            <input
              ref={fileRef}
              type="file"
              accept="image/*"
              hidden
              onChange={onPhoto}
            />
            {photoError ? (
              <p className="table-note" role="alert">
                {photoError}
              </p>
            ) : null}
          </div>
        </div>

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
        <div className="form-row">
          <label>
            Phone
            <input value={phone} onChange={(e) => setPhone(e.target.value)} />
          </label>
          <label>
            Location
            <input
              value={location}
              onChange={(e) => setLocation(e.target.value)}
            />
          </label>
        </div>
        <label>
          Headline
          <input
            value={headline}
            onChange={(e) => setHeadline(e.target.value)}
            placeholder="e.g. Senior Backend Engineer"
          />
        </label>
        <label>
          About
          <textarea value={bio} onChange={(e) => setBio(e.target.value)} rows={4} />
        </label>

        {save.error ? (
          <Notice icon="alert" title="Could not save">
            {save.error.message}
          </Notice>
        ) : null}

        {status === "applied" ? (
          <p className="inline-confirm">
            <Icon name="check" size={14} /> Saved.
          </p>
        ) : null}
        {status === "pending" ? (
          <p className="inline-confirm">
            <Icon name="clock" size={14} /> Submitted for superadmin approval.
          </p>
        ) : null}

        <div className="modal-actions">
          <button
            type="submit"
            className="button button--primary"
            disabled={save.pending}
          >
            {save.pending
              ? "Saving…"
              : needsApproval
                ? "Submit for approval"
                : "Save changes"}
          </button>
        </div>
      </form>
    </Panel>
  );
}

function PasswordForm() {
  const [current, setCurrent] = useState("");
  const [next, setNext] = useState("");
  const [done, setDone] = useState(false);

  const change = useAction(api.changeMyPassword);

  async function submit(event: React.FormEvent) {
    event.preventDefault();
    setDone(false);

    const result = await change.run(current, next);
    if (result) {
      setDone(true);
      setCurrent("");
      setNext("");
    }
  }

  return (
    <Panel title="Password" subtitle="Changing your password takes effect at once">
      <form className="form-stack" onSubmit={submit}>
        <label>
          Current password
          <input
            type="password"
            value={current}
            onChange={(e) => setCurrent(e.target.value)}
            required
          />
        </label>
        <label>
          New password
          <input
            type="password"
            value={next}
            onChange={(e) => setNext(e.target.value)}
            minLength={8}
            required
          />
        </label>

        {change.error ? (
          <Notice icon="alert" title="Could not change password">
            {change.error.message}
          </Notice>
        ) : null}
        {done ? (
          <p className="inline-confirm">
            <Icon name="check" size={14} /> Password changed.
          </p>
        ) : null}

        <div className="modal-actions">
          <button
            type="submit"
            className="button button--primary"
            disabled={change.pending}
          >
            {change.pending ? "Changing…" : "Change password"}
          </button>
        </div>
      </form>
    </Panel>
  );
}
