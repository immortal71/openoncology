"use client";

import * as ToastPrimitive from "@radix-ui/react-toast";
import { X } from "lucide-react";

export function Toaster() {
  return (
    <ToastPrimitive.Provider>
      <ToastPrimitive.Viewport className="fixed bottom-4 right-4 flex flex-col gap-2 z-50 max-w-sm" />
    </ToastPrimitive.Provider>
  );
}
