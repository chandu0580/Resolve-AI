import { Compass } from "lucide-react";
import { ButtonLink } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { EmptyState } from "@/components/ui/states";

export default function NotFound() {
  return (
    <div className="mx-auto max-w-xl py-10">
      <h1 className="sr-only">Page not found</h1>
      <Card>
        <EmptyState icon={Compass} title="Page not found" action={<ButtonLink href="/" variant="primary">Go to overview</ButtonLink>}>
          This address does not match any page in the ResolveAI console.
        </EmptyState>
      </Card>
    </div>
  );
}
