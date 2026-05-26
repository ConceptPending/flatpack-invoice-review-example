"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { checkAuth } from "./api";

export function useRequireAuth() {
  const [isAuth, setIsAuth] = useState<boolean | null>(null);
  const router = useRouter();

  useEffect(() => {
    checkAuth()
      .then(() => setIsAuth(true))
      .catch(() => {
        setIsAuth(false);
        router.push("/admin/login");
      });
  }, [router]);

  return isAuth;
}
