from collections import deque
from django.core.exceptions import ValidationError
from django.db import transaction
from .models import User


def find_available_binary_placement(sponsor_user):
    """
    Find the first available position (parent, position) in sponsor's binary referral tree
    using deterministic Breadth-First Search (BFS).
    Order of preference for each node: LEFT child first, then RIGHT child.
    """
    queue = deque([sponsor_user])
    visited = {sponsor_user.id}

    while queue:
        current = queue.popleft()

        # Check left slot
        left = current.left_child
        if not left:
            return current, User.ReferralPosition.LEFT

        # Check right slot
        right = current.right_child
        if not right:
            return current, User.ReferralPosition.RIGHT

        # Enqueue left child then right child for level-order traversal
        if left.id not in visited:
            visited.add(left.id)
            queue.append(left)

        if right.id not in visited:
            visited.add(right.id)
            queue.append(right)

    raise ValidationError('No available placement found in the referral tree.')


def get_root_ancestor(user):
    """
    Traverse the binary referral tree upwards through referred_by
    until reaching the top-level root ancestor.
    """
    current = user
    visited = {current.id}

    while current.referred_by:
        parent = current.referred_by
        if parent.id in visited:
            # Prevent potential infinite loop on circular references
            break
        visited.add(parent.id)
        current = parent

    return current


def count_descendants(user, visited=None):
    """
    Count all descendants strictly underneath the specified user node.
    """
    if not user:
        return 0

    if visited is None:
        visited = set()

    visited.add(user.id)
    count = 0
    queue = deque([user])

    while queue:
        curr = queue.popleft()
        children = [curr.left_child, curr.right_child]
        for child in children:
            if child and child.id not in visited:
                visited.add(child.id)
                count += 1
                queue.append(child)

    return count


def build_referral_tree(user, visited=None, max_depth=50):
    """
    Recursively serialize the binary referral tree rooted at user.
    """
    if not user or max_depth <= 0:
        return None

    if visited is None:
        visited = set()

    if user.id in visited:
        return None

    visited.add(user.id)

    left_child = user.left_child
    right_child = user.right_child

    return {
        'id': user.id,
        'email': user.email,
        'first_name': user.first_name,
        'last_name': user.last_name,
        'referral_code': user.referral_code,
        'referral_position': user.referral_position,
        'left': build_referral_tree(left_child, visited, max_depth - 1) if left_child else None,
        'right': build_referral_tree(right_child, visited, max_depth - 1) if right_child else None,
    }


def get_referral_stats(user):
    """
    Calculate team counts and direct placement details for a user's binary tree.
    """
    left_child = user.left_child
    right_child = user.right_child

    left_team_count = (1 + count_descendants(left_child)) if left_child else 0
    right_team_count = (1 + count_descendants(right_child)) if right_child else 0
    total_team_count = left_team_count + right_team_count

    return {
        'user_id': user.id,
        'email': user.email,
        'referral_code': user.referral_code,
        'left_team_count': left_team_count,
        'right_team_count': right_team_count,
        'total_team_count': total_team_count,
        'direct_left': {
            'id': left_child.id,
            'email': left_child.email,
            'first_name': left_child.first_name,
            'last_name': left_child.last_name,
            'referral_code': left_child.referral_code,
        } if left_child else None,
        'direct_right': {
            'id': right_child.id,
            'email': right_child.email,
            'first_name': right_child.first_name,
            'last_name': right_child.last_name,
            'referral_code': right_child.referral_code,
        } if right_child else None,
    }
