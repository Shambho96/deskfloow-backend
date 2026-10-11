import strawberry
from app.graphql.queries.user_queries import UserQuery
from app.graphql.queries.room_queries import RoomQuery
from app.graphql.mutations.user_mutations import UserMutation
from app.graphql.mutations.room_mutations import RoomMutation
from app.graphql.logging_extension import GraphQLLoggerExtension

@strawberry.type
class Query(UserQuery, RoomQuery):
    """Root GraphQL Query Schema."""
    pass

@strawberry.type
class Mutation(UserMutation, RoomMutation):
    """Root GraphQL Mutation Schema."""
    pass

schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    extensions=[GraphQLLoggerExtension]
)
