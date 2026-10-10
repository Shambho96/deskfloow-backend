import strawberry
from app.graphql.queries.user_queries import UserQuery
from app.graphql.mutations.user_mutations import UserMutation
from app.graphql.logging_extension import GraphQLLoggerExtension

@strawberry.type
class Query(UserQuery):
    """Root GraphQL Query Schema."""
    pass

@strawberry.type
class Mutation(UserMutation):
    """Root GraphQL Mutation Schema."""
    pass

schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    extensions=[GraphQLLoggerExtension]
)
