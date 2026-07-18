"""Admin-only pages and user-management API."""

from flask import jsonify, render_template, session

from .accounts import is_last_admin, purge_user
from .auth import admin_required
from .extensions import db
from .models import User


def init_app(app):

    @app.route('/admin/users')
    @admin_required
    def admin_manage_users():
        """Displays page for admins to manage users."""
        users = User.query.filter(User.id != session['user_id']).order_by(User.username).all()
        return render_template('admin_users.html', users=users)

    @app.route('/api/users/<int:user_id>/toggle_verify', methods=['POST'])
    @admin_required
    def api_toggle_verify_user(user_id):
        """Toggle user verification status."""
        user_to_modify = db.session.get(User, user_id)
        if not user_to_modify:
            return jsonify({"success": False, "message": "User not found."}), 404
        user_to_modify.is_verified = not user_to_modify.is_verified
        db.session.commit()
        return jsonify({
            "success": True,
            "verified": user_to_modify.is_verified,
            "new_text": "Unverify" if user_to_modify.is_verified else "Verify"
        })

    @app.route('/api/users/<int:user_id>/toggle_archive', methods=['POST'])
    @admin_required
    def api_toggle_archive_user(user_id):
        """Toggle a user's blocked state (stored as is_archived).

        Blocking keeps the account so the person can't log in *or* re-register
        (their email stays claimed) — the reversible way to keep someone out.
        Permanent removal is api_delete_user instead.
        """
        user_to_modify = db.session.get(User, user_id)
        if not user_to_modify:
            return jsonify({"success": False, "message": "User not found."}), 404
        if user_to_modify.id == session['user_id']:
            return jsonify({"success": False, "message": "You can't block your own account."}), 400
        # Blocking the last admin would leave the app adminless (and the next
        # registrant would be auto-promoted); don't allow it.
        if not user_to_modify.is_archived and is_last_admin(user_to_modify):
            return jsonify({"success": False,
                            "message": "Can't block the only administrator."}), 400
        user_to_modify.is_archived = not user_to_modify.is_archived
        db.session.commit()
        return jsonify({
            "success": True,
            "archived": user_to_modify.is_archived,
            "new_text": "Unblock" if user_to_modify.is_archived else "Block"
        })

    @app.route('/api/users/<int:user_id>/delete', methods=['POST'])
    @admin_required
    def api_delete_user(user_id):
        """Permanently delete a user and everything they own. Irreversible."""
        user_to_delete = db.session.get(User, user_id)
        if not user_to_delete:
            return jsonify({"success": False, "message": "User not found."}), 404
        if user_to_delete.id == session['user_id']:
            return jsonify({"success": False,
                            "message": "Delete your own account from the account page."}), 400
        if is_last_admin(user_to_delete):
            return jsonify({"success": False,
                            "message": "Can't delete the only administrator."}), 400
        purge_user(user_to_delete)
        return jsonify({"success": True, "deleted": True})
