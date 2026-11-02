import strawberry
from app.graphql.queries.user_queries import UserQuery
from app.graphql.queries.room_queries import RoomQuery
from app.graphql.queries.operations_queries import OperationsQuery
from app.graphql.mutations.user_mutations import UserMutation
from app.graphql.mutations.room_mutations import RoomMutation
from app.graphql.mutations.operations_mutations import OperationsMutation
from app.graphql.logging_extension import GraphQLLoggerExtension


@strawberry.type
class Query(UserQuery, RoomQuery, OperationsQuery):
    """Root GraphQL Query Schema."""

    pass


@strawberry.type
class Mutation(UserMutation, RoomMutation, OperationsMutation):
    """Root GraphQL Mutation Schema."""

    pass


schema = strawberry.Schema(query=Query, mutation=Mutation, extensions=[GraphQLLoggerExtension])
