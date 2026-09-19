from django.shortcuts import get_object_or_404
from drf_spectacular.utils import OpenApiResponse, extend_schema, inline_serializer
from rest_framework import serializers, status
from rest_framework.authtoken.models import Token
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import User
from .serializers import LoginSerializer, RegisterSerializer, UserSerializer
from .services import build_referral_tree, get_referral_stats, get_root_ancestor


@extend_schema(
    summary='Register a new customer',
    description='API endpoint for registering a new user with optional referral code and automatic binary placement.',
    request=RegisterSerializer,
    responses={
        201: inline_serializer(
            name='RegisterResponse',
            fields={
                'message': serializers.CharField(),
                'token': serializers.CharField(),
                'user': UserSerializer(),
            }
        ),
        400: OpenApiResponse(description='Validation error'),
    }
)
class RegisterView(APIView):
    """API endpoint for registering a new user."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RegisterSerializer(data=request.data)
        if serializer.is_valid():
            user = serializer.save()
            token, _ = Token.objects.get_or_create(user=user)
            return Response(
                {
                    'message': 'User registered successfully.',
                    'token': token.key,
                    'user': UserSerializer(user).data,
                },
                status=status.HTTP_201_CREATED
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    summary='User login',
    description='API endpoint for authenticating an existing user and issuing a token.',
    request=LoginSerializer,
    responses={
        200: inline_serializer(
            name='LoginResponse',
            fields={
                'message': serializers.CharField(),
                'token': serializers.CharField(),
                'user': UserSerializer(),
            }
        ),
        400: OpenApiResponse(description='Invalid credentials or validation error'),
    }
)
class LoginView(APIView):
    """API endpoint for authenticating an existing user and issuing a token."""
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = LoginSerializer(data=request.data, context={'request': request})
        if serializer.is_valid():
            user = serializer.validated_data['user']
            token, _ = Token.objects.get_or_create(user=user)
            return Response(
                {
                    'message': 'Login successful.',
                    'token': token.key,
                    'user': UserSerializer(user).data,
                },
                status=status.HTTP_200_OK
            )
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


@extend_schema(
    summary='User logout',
    description='API endpoint for logging out an authenticated user and invalidating the token.',
    request=None,
    responses={
        200: inline_serializer(
            name='LogoutResponse',
            fields={'message': serializers.CharField()}
        )
    }
)
class LogoutView(APIView):
    """API endpoint for logging out an authenticated user and invalidating the token."""
    permission_classes = [IsAuthenticated]

    def post(self, request):
        Token.objects.filter(user=request.user).delete()
        return Response(
            {'message': 'Successfully logged out.'},
            status=status.HTTP_200_OK
        )


@extend_schema(
    summary='User referral tree',
    description='Authenticated endpoint returning the full binary referral tree for a specific user (owner or staff only).',
    responses={
        200: OpenApiResponse(description='Binary referral tree structure'),
        403: OpenApiResponse(description='Permission denied'),
        404: OpenApiResponse(description='User not found'),
    }
)
class ReferralTreeView(APIView):
    """
    Authenticated endpoint returning the full binary referral tree for a specific user.
    Only the account owner or staff users may access this data.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        if request.user.id != user_id and not request.user.is_staff:
            return Response(
                {'error': 'You do not have permission to access this referral data.'},
                status=status.HTTP_403_FORBIDDEN
            )
        user = get_object_or_404(User, pk=user_id)
        tree_data = build_referral_tree(user)
        return Response(tree_data, status=status.HTTP_200_OK)


@extend_schema(
    summary='User referral root',
    description='Authenticated endpoint returning the root (topmost ancestor) in the referral lineage (owner or staff only).',
    responses={
        200: inline_serializer(
            name='ReferralRootResponse',
            fields={'root_user': UserSerializer()}
        ),
        403: OpenApiResponse(description='Permission denied'),
        404: OpenApiResponse(description='User not found'),
    }
)
class ReferralRootView(APIView):
    """
    Authenticated endpoint returning the root (topmost ancestor) in the referral lineage.
    Only the account owner or staff users may access this data.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        if request.user.id != user_id and not request.user.is_staff:
            return Response(
                {'error': 'You do not have permission to access this referral data.'},
                status=status.HTTP_403_FORBIDDEN
            )
        user = get_object_or_404(User, pk=user_id)
        root_user = get_root_ancestor(user)
        return Response(
            {
                'root_user': UserSerializer(root_user).data,
            },
            status=status.HTTP_200_OK
        )


@extend_schema(
    summary='User referral stats',
    description='Authenticated endpoint returning left, right, and total team counts for a user (owner or staff only).',
    responses={
        200: inline_serializer(
            name='ReferralStatsResponse',
            fields={
                'user_id': serializers.IntegerField(),
                'left_team_count': serializers.IntegerField(),
                'right_team_count': serializers.IntegerField(),
                'total_team_count': serializers.IntegerField(),
            }
        ),
        403: OpenApiResponse(description='Permission denied'),
        404: OpenApiResponse(description='User not found'),
    }
)
class ReferralStatsView(APIView):
    """
    Authenticated endpoint returning left, right, and total team counts for a user.
    Only the account owner or staff users may access this data.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, user_id):
        if request.user.id != user_id and not request.user.is_staff:
            return Response(
                {'error': 'You do not have permission to access this referral data.'},
                status=status.HTTP_403_FORBIDDEN
            )
        user = get_object_or_404(User, pk=user_id)
        stats = get_referral_stats(user)
        return Response(stats, status=status.HTTP_200_OK)
