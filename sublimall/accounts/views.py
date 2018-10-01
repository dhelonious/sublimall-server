# -*- coding: utf-8 -*-
import logging
from django.conf import settings
from django.db import transaction
from django.shortcuts import render
from django.http import HttpResponseRedirect
from django.views.generic import View
from django.views.generic import FormView
from django.views.generic import TemplateView
from django.views.decorators.debug import sensitive_post_parameters
from django.contrib import messages
from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.core.urlresolvers import reverse
from django.core.validators import validate_email
from django.core.exceptions import ValidationError
from django.utils.decorators import method_decorator

from urllib.parse import urljoin

from sublimall.utils import send_custom_mail
from sublimall.storage.models import Package
from sublimall.mixins import LoginRequiredMixin

from .models import Member
from .forms import LoginForm
from .utils import get_hash
from .utils import is_password_valid

logger = logging.getLogger(__name__)
auth_logger = logging.getLogger('sublimall.auth')

class MaintenanceView(TemplateView):
    template_name = "error.html"

    def get_context_data(self, *args, **kwargs):
        context = super().get_context_data(*args, **kwargs)
        context["title"] = "Sublimall is in maintenance"
        context[
            "error"
        ] = "<p>Sorry, Sublimall is under maintenance.</p>" "<p>Try again a little later.</p><p>Socketubs.</p>"
        context["hide_navbar"] = True
        return context


class LoginView(FormView):
    form_class = LoginForm
    template_name = "login.html"

    def get_form(self, form_class=None):
        if form_class is None:
            form_class = self.get_form_class()

        kwargs = self.get_form_kwargs()
        data = {
            "data": {},
            "files": kwargs.get("files"),
            "initial": kwargs.get("initial"),
            "prefix": kwargs.get("prefix"),
        }

        if self.request.method == "POST" and kwargs.get("data"):
            for field in ["next", "username", "csrfmiddlewaretoken", "password"]:
                data["data"][field] = kwargs["data"].get(field)
            data["data"]["username"] = data["data"]["username"].lower()
        else:
            data = kwargs

        return form_class(**data)

    def get(self, request):
        if request.user.is_authenticated():
            return HttpResponseRedirect(reverse("account"))
        return super(LoginView, self).get(request)

    def form_valid(self, form):
        auth_login(self.request, form.get_user())
        if self.request.session.test_cookie_worked():
            self.request.session.delete_test_cookie()
        return HttpResponseRedirect(reverse("account"))

    def form_invalid(self, form):
        if self.request.method == "POST":
            auth_logger.error("Login Fail {} by {}".format(
                self.request.POST.get("username"),
                self.request.META.get("HTTP_X_FORWARDED_FOR"),
            ))
        return self.render_to_response(self.get_context_data(form=form))

    @method_decorator(sensitive_post_parameters("password"))
    def dispatch(self, request, *args, **kwargs):
        request.session.set_test_cookie()
        return super(LoginView, self).dispatch(request, *args, **kwargs)


class LogoutView(View):
    def get(self, request):
        auth_logout(request)
        messages.info(request, "You have been logged out. See you soon.")
        return HttpResponseRedirect(reverse("home"))


class RegistrationView(View):
    def get(self, request):
        if request.user.is_authenticated():
            return HttpResponseRedirect(reverse("account"))
        current_user_count = Member.objects.all().count()
        if current_user_count >= settings.MAX_MEMBER:
            msg = (
                "I'm sorry about that, don't forget that it's "
                "a beta version of Sublimall. <br /><strong>Registrations "
                "will been soon re-opened!</strong></p><p><em>Geoffrey.</em>"
            )
            return render(
                request, "error.html", {"title": "Max registration reach", "error": msg}
            )
        return render(request, "registration.html")

    @transaction.atomic
    def post(self, request):
        template = "registration.html"

        current_user_count = Member.objects.all().count()
        if current_user_count >= settings.MAX_MEMBER:
            logger.warning("Max registration number reached")
            return render(
                request,
                template,
                {
                    "form": {
                        "errors": "Max member reach. I'm sorry about that, "
                        "don't forget that it's a beta version of Sublimall. "
                        "Registrations will been soon re-opened!"
                    }
                },
            )

        email = request.POST.get("email", "").lower()
        email2 = request.POST.get("email2", "").lower()
        password = request.POST.get("password")
        password2 = request.POST.get("password2")

        if not email:
            return render(
                request, template, {"form": {"errors": "Email can't be empty."}}
            )
        if not password:
            return render(
                request, template, {"form": {"errors": "Password can't be empty."}}
            )

        try:
            validate_email(email)
        except ValidationError:
            return render(
                request, template, {"form": {"errors": "Need a valid email."}}
            )

        password_validation, error = is_password_valid(password)
        if not password_validation:
            return render(request, template, {"form": {"errors": error}})

        if password != password2:
            return render(
                request, template, {"form": {"errors": "Password doesn't match."}}
            )

        if email != email2:
            return render(
                request, template, {"form": {"errors": "Emails doesn't match."}}
            )

        if Member.objects.filter(email=email).exists():
            return render(
                request, template, {"form": {"errors": "Email already used."}}
            )

        try:
            member = Member(email=email, is_active=False)
            member.set_password(password)
            member.full_clean()
            member.save()

            member.send_registration_confirmation()

        except Exception:
            logger.error(
                "Registration unhandled exception",
                exc_info=True,
                extra={"request": request},
            )
            return render(
                request,
                template,
                {
                    "form": {
                        "errors": "Error while creating your account. "
                        "A report have been sent. Sorry about that."
                    }
                },
            )

        messages.success(
            request,
            "You'll receive an email soon, check it to confirm "
            "your account. See you soon!",
        )
        return HttpResponseRedirect(reverse("login"))


class ResendRegistrationView(View):
    def get(self, request):
        if request.user.is_authenticated():
            return HttpResponseRedirect(reverse("account"))
        return render(request, "resend-registration-link.html")

    def post(self, request):
        if request.user.is_authenticated():
            return HttpResponseRedirect(reverse("account"))

        email = request.POST.get("email")
        msg = (
            "If you give me a valid email, you'll " "received an email with some help."
        )

        try:
            member = Member.objects.get(email=email)
        except Member.DoesNotExist:
            messages.info(request, msg)
            return HttpResponseRedirect(reverse("login"))

        member.send_registration_confirmation(reset_key=True)
        messages.info(request, msg)
        return HttpResponseRedirect(reverse("login"))


class RegistrationConfirmationView(View):
    def get(self, request, key, pk):
        try:
            member = Member.objects.get(pk=pk, registration_key=key)
        except Member.DoesNotExist:
            member = None

        if member is None:
            return render(
                request,
                "error.html",
                {"title": "Error", "error": "Invalid key or account already active."},
            )

        if member.is_active:
            messages.info(request, "Your account is already active.")
            member.registration_key = None
            member.save()
            return HttpResponseRedirect(reverse("login"))

        member.is_active = True
        member.registration_key = None
        member.save()

        messages.success(request, "Your account is now active.")

        return HttpResponseRedirect(reverse("login"))


class AccountView(LoginRequiredMixin, View):
    def get(self, request):
        member = request.user
        packages = Package.objects.filter(member=member)

        return render(
            request,
            "account.html",
            {
                "storage_limit": member.get_storage_limit(),
                "is_staff": member.is_staff,
                "date_joined": member.date_joined,
                "packages": packages,
                "api_key": member.api_key,
                "email": member.email,
            },
        )


class AccountDeleteView(View, LoginRequiredMixin):
    def get(self, request):
        return render(request, "account-delete.html")

    @transaction.atomic
    def post(self, request):
        if request.user.is_staff:
            messages.warning(request, "Impossible to remove staff account.")
            return HttpResponseRedirect(reverse("account"))

        email = request.user.email
        request.user.package_set.all().delete()
        request.user.delete()
        messages.success(
            request, "Your account has been removed with success. See you soon!"
        )

        send_custom_mail(
            "Sublimall.org account deleted",
            email,
            "account-deleted",
            {"feedback_email": settings.FROM_EMAIL},
        )
        return HttpResponseRedirect(reverse("home"))


class GenerateAPIKey(LoginRequiredMixin, View):
    def get(self, request):
        member = request.user
        member.api_key = get_hash()
        member.save()
        return HttpResponseRedirect(reverse("account"))


class PasswordRecoveryView(View):
    def get(self, request):
        return render(request, "password-recovery.html")

    def post(self, request):
        email = request.POST.get("email")
        msg = (
            "If you give me a valid email, " "you'll received an email with some help."
        )
        try:
            member = Member.objects.get(email=email)
        except Member.DoesNotExist:
            messages.info(request, msg)
            return render(request, "password-recovery.html")

        member.password_key = get_hash()
        member.save()

        send_custom_mail(
            "Sublimall.org password recovery",
            member.email,
            "password-recovery",
            {
                "password_recovery_link": urljoin(
                    settings.SITE_URL,
                    reverse(
                        "password-recovery-confirmation",
                        args=[member.id, member.password_key],
                    ),
                )
            },
        )

        messages.info(request, msg)
        return HttpResponseRedirect(reverse("login"))


class PasswordRecoveryConfirmationView(View):
    def get(self, request, pk, key):
        try:
            member = Member.objects.get(pk=pk, password_key=key)
        except Member.DoesNotExist:
            member = None

        if member is None:
            return render(
                request, "error.html", {"title": "Error", "error": "Invalid key."}
            )

        return render(
            request, "password-recovery-form.html", {"id": pk, "password_key": key}
        )

    def post(self, request, pk, key):
        password = request.POST.get("password")
        password2 = request.POST.get("password2")

        template = "password-recovery-form.html"

        try:
            member = Member.objects.get(pk=pk, password_key=key)
        except Member.DoesNotExist:
            member = None

        if member is None:
            return render(
                request, "error.html", {"title": "Error", "error": "Invalid key."}
            )

        password_validation, error = is_password_valid(password)
        if not password_validation:
            return render(
                request,
                template,
                {"form": {"errors": error}, "pk": pk, "password_key": key},
            )

        if password != password2:
            return render(
                request,
                template,
                {
                    "form": {"errors": "Password doesn't match."},
                    "pk": pk,
                    "password_key": key,
                },
            )

        member.set_password(password)
        member.save()

        messages.success(request, "Password changed with success!")
        return HttpResponseRedirect(reverse("login"))
