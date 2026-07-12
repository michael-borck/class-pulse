"""Admin-only pages and user-management API."""

from flask import jsonify, render_template, session

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
        """Toggle user archive status."""
        user_to_modify = db.session.get(User, user_id)
        if not user_to_modify:
            return jsonify({"success": False, "message": "User not found."}), 404
        if user_to_modify.id == session['user_id']:
            return jsonify({"success": False, "message": "Cannot archive self."}), 400
        user_to_modify.is_archived = not user_to_modify.is_archived
        db.session.commit()
        return jsonify({
            "success": True,
            "archived": user_to_modify.is_archived,
            "new_text": "Unarchive" if user_to_modify.is_archived else "Archive"
        })
