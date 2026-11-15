import strawberry
from app.graphql.queries.user_queries import UserQuery
from app.graphql.queries.room_queries import RoomQuery
from app.graphql.queries.operations_queries import OperationsQuery
from app.graphql.queries.guest_queries import GuestQuery
from app.graphql.queries.analytics_queries import AnalyticsQuery
from app.graphql.queries.reporting_queries import ReportingQuery
from app.graphql.mutations.user_mutations import UserMutation
from app.graphql.mutations.room_mutations import RoomMutation
from app.graphql.mutations.operations_mutations import OperationsMutation
from app.graphql.mutations.guest_mutations import GuestMutation
from app.graphql.mutations.reporting_mutations import ReportingMutation
from app.graphql.logging_extension import GraphQLLoggerExtension


@strawberry.type
class Query(UserQuery, RoomQuery, OperationsQuery, GuestQuery, AnalyticsQuery, ReportingQuery):
    """Root GraphQL Query Schema."""

    pass


@strawberry.type
class Mutation(UserMutation, RoomMutation, OperationsMutation, GuestMutation, ReportingMutation):
    """Root GraphQL Mutation Schema."""

    pass


schema = strawberry.Schema(query=Query, mutation=Mutation, extensions=[GraphQLLoggerExtension])
