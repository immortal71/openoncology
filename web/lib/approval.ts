export type Approval = {
  approved: boolean;
  label: string;
  qualifier: string | null;
  differentIndication: boolean;
};

export function parseApproval(raw: string | null | undefined): Approval {
  const text = raw?.trim();
  if (!text) return { approved: false, label: "Approval status unknown", qualifier: null, differentIndication: false };

  const [head, ...rest] = text.split(/\s+[—–-]\s+/);
  const qualifier = rest.join(" — ").trim() || null;
  const approved = /\bfda[\s-]+approved\b/i.test(head);

  return {
    approved,
    label: approved ? "FDA approved" : head.trim(),
    qualifier,
    differentIndication: qualifier ? /different indication|off[\s-]label/i.test(qualifier) : false,
  };
}
