import { ArrowLeft } from "lucide-react";
import { Link } from "react-router";
import { Card, PageHeader } from "@/components/ui";
export function NotFound() {
  return (
    <>
      <PageHeader
        eyebrow="404"
        title="Page not found"
        description="The requested SIRE page does not exist."
      />
      <Card>
        <Link className="button button-primary" to="/">
          <ArrowLeft size={16} /> Return to overview
        </Link>
      </Card>
    </>
  );
}
