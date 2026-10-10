import logging
from strawberry.extensions import SchemaExtension

logger = logging.getLogger("deskflow.graphql")

class GraphQLLoggerExtension(SchemaExtension):
    """
    Custom Strawberry GraphQL extension that logs compact query/mutation root field names.
    Output Format: [GRAPHQL] query MyQuery { teamMembers | Context: user_id=1 (OWNER, outlet=1)
    """
    def on_operation(self):
        ctx = self.execution_context
        raw_query = (ctx.query or "").strip()
        
        # Clean lines
        lines = [l.strip() for l in raw_query.splitlines() if l.strip() and not l.strip().startswith("#")]
        joined = " ".join(lines)
        
        # Format compact snippet (e.g. "query MyQuery { teamMembers")
        if "{" in joined:
            if joined.startswith("{"):
                first_part = joined.lstrip("{").strip()
                root_field = first_part.split()[0].split("(")[0] if first_part else ""
                snippet = f"{{ {root_field}"
            else:
                parts = [p.strip() for p in joined.split("{") if p.strip()]
                head = parts[0] if parts else ""
                root_field = parts[1].split()[0].split("(")[0] if len(parts) > 1 else ""
                snippet = f"{head} {{ {root_field}" if root_field else head
        else:
            snippet = joined[:50]

        user_info = "Anonymous"
        if ctx.context and hasattr(ctx.context, "user") and ctx.context.user:
            u = ctx.context.user
            user_info = f"user_id={u.user_id} ({u.role}, outlet={u.outlet_id})"

        print(f"[GRAPHQL] {snippet} | Context: {user_info}", flush=True)
        yield
