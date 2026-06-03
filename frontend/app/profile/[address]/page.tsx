"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { API_BASE } from "../../../lib/api";
import { WhaleProfilePanel } from "../../../components/profile/whale-profile-panel";
import { truncateAddress } from "../../../lib/format";

export default function ProfilePage() {
  const params = useParams();
  const address = decodeURIComponent((params.address as string) || "");
  const [profile, setProfile] = useState<any>(null);
  const [loading, setLoading] = useState(true);

  useEffect(() => {
    if (!address) return;
    setLoading(true);
    fetch(`${API_BASE}/api/v1/whales/profile/${address}`)
      .then((r) => (r.ok ? r.json() : null))
      .then((data) => setProfile(data))
      .finally(() => setLoading(false));
  }, [address]);

  return (
    <div className="mx-auto max-w-lg p-4 lg:p-6">
      <Link href="/" className="font-mono text-xs text-accent-glow hover:underline">
        ← Dashboard
      </Link>
      <h1 className="mt-4 font-display text-xl font-bold text-text-primary">
        Whale profile
      </h1>
      <p className="font-mono text-xs text-text-muted">{truncateAddress(address)}</p>

      <div className="panel mt-6 p-4">
        {loading ? (
          <div className="flex justify-center py-12">
            <div className="h-8 w-8 animate-spin rounded-full border-2 border-border border-t-accent-glow" />
          </div>
        ) : (
          <WhaleProfilePanel
            profile={profile}
            selectedAddress={address}
            watchlist={[]}
          />
        )}
      </div>

      <Link
        href={`/?wallet=${address}`}
        className="btn-primary mt-4 inline-block text-center"
      >
        Open in dashboard tape
      </Link>
    </div>
  );
}
