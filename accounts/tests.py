
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.urls import reverse
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.test import APITestCase

from .models import User
from .services import (
    build_referral_tree,
    find_available_binary_placement,
    get_referral_stats,
    get_root_ancestor,
)

User = get_user_model()


class UserModelTests(APITestCase):
    """Unit tests for the custom User model and manager."""

    def test_create_user_successful(self):
        user = User.objects.create_user(
            email='user@example.com',
            password='securepassword123',
            first_name='John',
            last_name='Doe'
        )
        self.assertEqual(user.email, 'user@example.com')
        self.assertTrue(user.check_password('securepassword123'))
        self.assertFalse(user.is_staff)
        self.assertFalse(user.is_superuser)
        self.assertTrue(user.is_active)
        self.assertTrue(bool(user.referral_code))

    def test_create_user_missing_email_raises_error(self):
        with self.assertRaises(ValueError):
            User.objects.create_user(
                email='',
                password='securepassword123',
                first_name='John',
                last_name='Doe'
            )

    def test_create_superuser_successful(self):
        admin_user = User.objects.create_superuser(
            email='admin@example.com',
            password='adminpassword123',
            first_name='Admin',
            last_name='User'
        )
        self.assertEqual(admin_user.email, 'admin@example.com')
        self.assertTrue(admin_user.is_staff)
        self.assertTrue(admin_user.is_superuser)
        self.assertTrue(admin_user.is_active)

    def test_unique_referral_code_generation(self):
        user1 = User.objects.create_user(
            email='user1@example.com',
            password='password123',
            first_name='Alice',
            last_name='Smith'
        )
        user2 = User.objects.create_user(
            email='user2@example.com',
            password='password123',
            first_name='Bob',
            last_name='Jones'
        )
        self.assertIsNotNone(user1.referral_code)
        self.assertIsNotNone(user2.referral_code)
        self.assertNotEqual(user1.referral_code, user2.referral_code)

    def test_user_str_representation(self):
        user = User.objects.create_user(
            email='struser@example.com',
            password='password123',
            first_name='Str',
            last_name='User'
        )
        self.assertEqual(str(user), 'struser@example.com')

    def test_superuser_without_staff_fails(self):
        with self.assertRaises(ValueError):
            User.objects.create_superuser(
                email='invalidadmin@example.com',
                password='password123',
                first_name='Admin',
                last_name='User',
                is_staff=False
            )

    def test_left_and_right_child_properties(self):
        parent = User.objects.create_user(email='parent@example.com', password='p', first_name='P', last_name='U')
        left = User.objects.create_user(email='left@example.com', password='p', first_name='L', last_name='U', referred_by=parent, referral_position=User.ReferralPosition.LEFT)
        right = User.objects.create_user(email='right@example.com', password='p', first_name='R', last_name='U', referred_by=parent, referral_position=User.ReferralPosition.RIGHT)

        self.assertEqual(parent.left_child, left)
        self.assertEqual(parent.right_child, right)

    def test_user_clean_self_referral_raises_validation_error(self):
        user = User.objects.create_user(email='selfparent@example.com', password='p', first_name='S', last_name='P')
        user.referred_by = user
        with self.assertRaises(Exception):
            user.clean()


class AuthAPITests(APITestCase):
    """Integration tests for registration, login, and logout APIs."""

    def setUp(self):
        self.register_url = reverse('auth-register')
        self.login_url = reverse('auth-login')
        self.logout_url = reverse('auth-logout')

        self.user_data = {
            'email': 'customer@example.com',
            'password': 'password123',
            'first_name': 'Jane',
            'last_name': 'Doe',
        }

    def test_successful_registration(self):
        response = self.client.post(self.register_url, self.user_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn('token', response.data)
        self.assertIn('user', response.data)
        self.assertEqual(response.data['user']['email'], 'customer@example.com')
        self.assertTrue(bool(response.data['user']['referral_code']))
        self.assertTrue(User.objects.filter(email='customer@example.com').exists())

    def test_duplicate_registration_validation(self):
        self.client.post(self.register_url, self.user_data, format='json')
        response = self.client.post(self.register_url, self.user_data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('email', response.data)

    def test_registration_with_valid_referral_code(self):
        referrer = User.objects.create_user(
            email='referrer@example.com',
            password='password123',
            first_name='Referrer',
            last_name='User'
        )

        data = {
            'email': 'referee@example.com',
            'password': 'password123',
            'first_name': 'Referee',
            'last_name': 'User',
            'referral_code': referrer.referral_code,
        }
        response = self.client.post(self.register_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        
        referee = User.objects.get(email='referee@example.com')
        self.assertEqual(referee.referred_by, referrer)
        self.assertEqual(referee.referral_position, User.ReferralPosition.LEFT)
        self.assertEqual(response.data['user']['referred_by_code'], referrer.referral_code)
        self.assertEqual(response.data['user']['referral_position'], 'LEFT')

    def test_registration_with_invalid_referral_code(self):
        data = {
            'email': 'referee2@example.com',
            'password': 'password123',
            'first_name': 'Referee',
            'last_name': 'Two',
            'referral_code': 'NONEXISTENTCODE',
        }
        response = self.client.post(self.register_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn('referral_code', response.data)

    def test_registration_self_referral_rejected(self):
        user = User.objects.create_user(
            email='selfref@example.com',
            password='password123',
            first_name='Self',
            last_name='Ref'
        )
        data = {
            'email': 'selfref@example.com',
            'password': 'password123',
            'first_name': 'Self',
            'last_name': 'Ref',
            'referral_code': user.referral_code,
        }
        response = self.client.post(self.register_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_registration_missing_required_fields_fails(self):
        response = self.client.post(self.register_url, {'email': 'incomplete@example.com'}, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_registration_short_password_fails(self):
        data = {
            'email': 'shortpass@example.com',
            'password': '123',
            'first_name': 'Short',
            'last_name': 'Pass',
        }
        response = self.client.post(self.register_url, data, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_successful_and_returns_token(self):
        User.objects.create_user(
            email='logintest@example.com',
            password='Password123!',
            first_name='Login',
            last_name='User'
        )
        response = self.client.post(self.login_url, {
            'email': 'logintest@example.com',
            'password': 'Password123!',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn('token', response.data)
        self.assertEqual(response.data['user']['email'], 'logintest@example.com')

    def test_login_inactive_user_fails(self):
        user = User.objects.create_user(
            email='inactiveuser@example.com',
            password='Password123!',
            first_name='Inactive',
            last_name='User'
        )
        user.is_active = False
        user.save()

        response = self.client.post(self.login_url, {
            'email': 'inactiveuser@example.com',
            'password': 'Password123!',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_login_invalid_credentials_fails(self):
        User.objects.create_user(
            email='logintest@example.com',
            password='Password123!',
            first_name='Login',
            last_name='User'
        )
        response = self.client.post(self.login_url, {
            'email': 'logintest@example.com',
            'password': 'WrongPassword',
        }, format='json')
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_logout_invalidates_token(self):
        user = User.objects.create_user(
            email='logoutuser@example.com',
            password='Password123!',
            first_name='Logout',
            last_name='User'
        )
        token = Token.objects.create(user=user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {token.key}')
        response = self.client.post(self.logout_url)
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(Token.objects.filter(key=token.key).exists())

    def test_unauthenticated_logout_rejected(self):
        response = self.client.post(self.logout_url)
        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class BinaryReferralNetworkTests(APITestCase):
    """Tests for Binary Referral tree placement, root finding, and team statistics."""

    def setUp(self):
        self.root_user = User.objects.create_user(
            email='root@example.com',
            password='password123',
            first_name='Root',
            last_name='Leader'
        )
        self.token = Token.objects.create(user=self.root_user)
        self.register_url = reverse('auth-register')

    def test_binary_placement_order_bfs(self):
        """
        Test BFS spillover placement:
        1st referral -> Under Root as LEFT
        2nd referral -> Under Root as RIGHT
        3rd referral -> Under Child 1 (LEFT child) as LEFT
        4th referral -> Under Child 1 (LEFT child) as RIGHT
        5th referral -> Under Child 2 (RIGHT child) as LEFT
        """
        # 1st referral -> Root LEFT
        parent, pos = find_available_binary_placement(self.root_user)
        self.assertEqual(parent, self.root_user)
        self.assertEqual(pos, User.ReferralPosition.LEFT)
        u1 = User.objects.create_user(email='u1@example.com', password='p', first_name='U1', last_name='L', referred_by=parent, referral_position=pos, sponsor=self.root_user)

        # 2nd referral -> Root RIGHT
        parent, pos = find_available_binary_placement(self.root_user)
        self.assertEqual(parent, self.root_user)
        self.assertEqual(pos, User.ReferralPosition.RIGHT)
        u2 = User.objects.create_user(email='u2@example.com', password='p', first_name='U2', last_name='L', referred_by=parent, referral_position=pos, sponsor=self.root_user)

        # 3rd referral -> Under u1 as LEFT
        parent, pos = find_available_binary_placement(self.root_user)
        self.assertEqual(parent, u1)
        self.assertEqual(pos, User.ReferralPosition.LEFT)
        u3 = User.objects.create_user(email='u3@example.com', password='p', first_name='U3', last_name='L', referred_by=parent, referral_position=pos, sponsor=self.root_user)

        # 4th referral -> Under u1 as RIGHT
        parent, pos = find_available_binary_placement(self.root_user)
        self.assertEqual(parent, u1)
        self.assertEqual(pos, User.ReferralPosition.RIGHT)
        u4 = User.objects.create_user(email='u4@example.com', password='p', first_name='U4', last_name='L', referred_by=parent, referral_position=pos, sponsor=self.root_user)

        # 5th referral -> Under u2 as LEFT
        parent, pos = find_available_binary_placement(self.root_user)
        self.assertEqual(parent, u2)
        self.assertEqual(pos, User.ReferralPosition.LEFT)
        u5 = User.objects.create_user(email='u5@example.com', password='p', first_name='U5', last_name='L', referred_by=parent, referral_position=pos, sponsor=self.root_user)

    def test_duplicate_placement_rejected_by_db_constraint(self):
        User.objects.create_user(
            email='child_left@example.com',
            password='password123',
            first_name='Child',
            last_name='Left',
            referred_by=self.root_user,
            referral_position=User.ReferralPosition.LEFT
        )
        with self.assertRaises(IntegrityError):
            User.objects.create_user(
                email='child_left_duplicate@example.com',
                password='password123',
                first_name='Child',
                last_name='Duplicate',
                referred_by=self.root_user,
                referral_position=User.ReferralPosition.LEFT
            )

    def test_referral_tree_api(self):
        # Build a small tree: Root -> Left (B), Right (C); B -> Left (D)
        b = User.objects.create_user(email='b@example.com', password='p', first_name='B', last_name='User', referred_by=self.root_user, referral_position='LEFT')
        c = User.objects.create_user(email='c@example.com', password='p', first_name='C', last_name='User', referred_by=self.root_user, referral_position='RIGHT')
        d = User.objects.create_user(email='d@example.com', password='p', first_name='D', last_name='User', referred_by=b, referral_position='LEFT')

        tree_url = reverse('referral-tree', kwargs={'user_id': self.root_user.id})
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        response = self.client.get(tree_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['id'], self.root_user.id)
        self.assertEqual(response.data['left']['id'], b.id)
        self.assertEqual(response.data['right']['id'], c.id)
        self.assertEqual(response.data['left']['left']['id'], d.id)
        self.assertIsNone(response.data['left']['right'])
        self.assertIsNone(response.data['right']['left'])

    def test_referral_root_api(self):
        b = User.objects.create_user(email='b@example.com', password='p', first_name='B', last_name='User', referred_by=self.root_user, referral_position='LEFT')
        c = User.objects.create_user(email='c@example.com', password='p', first_name='C', last_name='User', referred_by=b, referral_position='LEFT')
        d = User.objects.create_user(email='d@example.com', password='p', first_name='D', last_name='User', referred_by=c, referral_position='RIGHT')

        d_token = Token.objects.create(user=d)
        root_url = reverse('referral-root', kwargs={'user_id': d.id})
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {d_token.key}')
        response = self.client.get(root_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['root_user']['id'], self.root_user.id)
        self.assertEqual(response.data['root_user']['email'], 'root@example.com')

    def test_referral_stats_api(self):
        """
        Tree:
               Root
              /    \
             B      C
            / \
           D   E
        Root stats: left = 3 (B, D, E), right = 1 (C), total = 4
        """
        b = User.objects.create_user(email='b@example.com', password='p', first_name='B', last_name='User', referred_by=self.root_user, referral_position='LEFT')
        c = User.objects.create_user(email='c@example.com', password='p', first_name='C', last_name='User', referred_by=self.root_user, referral_position='RIGHT')
        d = User.objects.create_user(email='d@example.com', password='p', first_name='D', last_name='User', referred_by=b, referral_position='LEFT')
        e = User.objects.create_user(email='e@example.com', password='p', first_name='E', last_name='User', referred_by=b, referral_position='RIGHT')

        stats_url = reverse('referral-stats', kwargs={'user_id': self.root_user.id})
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.token.key}')
        response = self.client.get(stats_url)

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data['left_team_count'], 3)
        self.assertEqual(response.data['right_team_count'], 1)
        self.assertEqual(response.data['total_team_count'], 4)
        self.assertEqual(response.data['direct_left']['id'], b.id)
        self.assertEqual(response.data['direct_right']['id'], c.id)

    def test_referral_service_helpers(self):
        b = User.objects.create_user(email='b_svc@example.com', password='p', first_name='B', last_name='User', referred_by=self.root_user, referral_position='LEFT')
        c = User.objects.create_user(email='c_svc@example.com', password='p', first_name='C', last_name='User', referred_by=b, referral_position='LEFT')

        # Test root ancestor
        self.assertEqual(get_root_ancestor(c), self.root_user)
        self.assertEqual(get_root_ancestor(self.root_user), self.root_user)

        # Test build tree
        tree = build_referral_tree(self.root_user)
        self.assertEqual(tree['id'], self.root_user.id)
        self.assertEqual(tree['left']['id'], b.id)

        # Test stats helper
        stats = get_referral_stats(self.root_user)
        self.assertEqual(stats['left_team_count'], 2)
        self.assertEqual(stats['right_team_count'], 0)

    def test_unauthenticated_referral_api_access_rejected(self):
        tree_url = reverse('referral-tree', kwargs={'user_id': self.root_user.id})
        root_url = reverse('referral-root', kwargs={'user_id': self.root_user.id})
        stats_url = reverse('referral-stats', kwargs={'user_id': self.root_user.id})

        self.assertEqual(self.client.get(tree_url).status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(self.client.get(root_url).status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertEqual(self.client.get(stats_url).status_code, status.HTTP_401_UNAUTHORIZED)

    def test_nonexistent_user_referral_api_returns_404(self):
        staff_user = User.objects.create_superuser(
            email='staff_lookup@example.com',
            password='password123',
            first_name='Staff',
            last_name='Admin'
        )
        staff_token = Token.objects.create(user=staff_user)
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {staff_token.key}')
        tree_url = reverse('referral-tree', kwargs={'user_id': 99999})
        root_url = reverse('referral-root', kwargs={'user_id': 99999})
        stats_url = reverse('referral-stats', kwargs={'user_id': 99999})

        self.assertEqual(self.client.get(tree_url).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.get(root_url).status_code, status.HTTP_404_NOT_FOUND)
        self.assertEqual(self.client.get(stats_url).status_code, status.HTTP_404_NOT_FOUND)


class ReferralAccessControlTests(APITestCase):
    """Tests to verify referral endpoints access control (owner or staff only)."""

    def setUp(self):
        self.owner = User.objects.create_user(
            email='owner@example.com',
            password='password123',
            first_name='Owner',
            last_name='User'
        )
        self.owner_token = Token.objects.create(user=self.owner)

        self.other_user = User.objects.create_user(
            email='other@example.com',
            password='password123',
            first_name='Other',
            last_name='User'
        )
        self.other_token = Token.objects.create(user=self.other_user)

        self.staff_user = User.objects.create_superuser(
            email='staff@example.com',
            password='password123',
            first_name='Staff',
            last_name='Admin'
        )
        self.staff_token = Token.objects.create(user=self.staff_user)

    def test_referral_endpoints_access_control_owner_and_staff_allowed(self):
        endpoints = [
            reverse('referral-tree', kwargs={'user_id': self.owner.id}),
            reverse('referral-root', kwargs={'user_id': self.owner.id}),
            reverse('referral-stats', kwargs={'user_id': self.owner.id}),
        ]
        # Owner access allowed
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.owner_token.key}')
        for url in endpoints:
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)

        # Staff access allowed
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.staff_token.key}')
        for url in endpoints:
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_200_OK)

    def test_referral_endpoints_access_control_unauthorized_user_forbidden(self):
        endpoints = [
            reverse('referral-tree', kwargs={'user_id': self.owner.id}),
            reverse('referral-root', kwargs={'user_id': self.owner.id}),
            reverse('referral-stats', kwargs={'user_id': self.owner.id}),
        ]
        # Unaffiliated user access forbidden
        self.client.credentials(HTTP_AUTHORIZATION=f'Token {self.other_token.key}')
        for url in endpoints:
            response = self.client.get(url)
            self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
            self.assertIn('permission', response.data.get('error', '').lower())


