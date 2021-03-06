from django.contrib import messages
from django.core.exceptions import ObjectDoesNotExist
from django.contrib.auth.decorators import login_required
from django.contrib.auth.mixins import LoginRequiredMixin
# For the warnings ^
from django.conf import settings
from django.shortcuts import render, get_object_or_404, redirect
from django.views.generic import ListView, DetailView, View
from django.utils import timezone
from .forms import CheckoutForm
from .models import Item, OrderItem, Order, BillingAddress, Payment

# Create your views here.

import stripe
stripe.api_key = settings.STRIPE_SECRET_KEY

""" def HomeView(request):
    context = {
        'items': Item.objects.all()
    }
    return render(request, "home-page.html", context) """


""" def ProductView(request):
    context = {
        'items': Item.objects.all()
    }
    return render(request, "product-page.html", context) """


def AboutView(request):
    return render(request, "about-page.html", {})


# either primary key or slug
class ProductView(DetailView):
    model = Item
    template_name = "product-page.html"


class HomeView(ListView):
    model = Item
    # How many items per page
    paginate_by = 10
    template_name = "home-page.html"


# View as we do not want to inherit a slug or pk
class OrderSummary(LoginRequiredMixin, View):
    def get(self, *args, **kwards):
        try:
            order = Order.objects.get(user=self.request.user, ordered=False)
            context = {
                'object': order
            }
            return render(self.request, 'order_summary.html', context)
        except ObjectDoesNotExist:
            messages.error(
                self.request, "You do not have any items in the cart")
            return redirect("/")


# def CheckoutView(request):
#     return render(request, "checkout-page.html", {})

class CheckoutView(View):
    def get(self, *args, **kwargs):
        # The form
        order = Order.objects.get(user=self.request.user, ordered=False)
        form = CheckoutForm()
        context = {
            'order': order,
            'form': form,
        }
        return render(self.request, "checkout-page.html", context)

    def post(self, *args, **kwargs):
        form = CheckoutForm(self.request.POST or None)
        try:
            order = Order.objects.get(user=self.request.user, ordered=False)
            if form.is_valid():
                # print(form.cleaned_data)
                street_address = form.cleaned_data.get('street_address')
                apartment_address = form.cleaned_data.get('apartment_address')
                country = form.cleaned_data.get('country')
                zip_code = form.cleaned_data.get('zip_code')
                # TODO
                # same_shipping_address = form.cleaned_data.get('same_shipping_address')
                # save_info = form.cleaned_data.get('save_info')
                payment_option = form.cleaned_data.get('payment_option')
                billing_address = BillingAddress(
                    user=self.request.user,
                    street_address=street_address,
                    apartment_address=apartment_address,
                    country=country,
                    zip_code=zip_code,
                )
                billing_address.save()
                order.billing_address = billing_address
                order.save()
                # TODO: redirect payment

                if payment_option == 'S':
                    return redirect('core:payment', payment_option='stripe')
                elif payment_option == 'P':
                    return redirect('core:payment', payment_option='paypal')
                else:
                    messages.warning(self.request, "Invalid payment option")
                    return redirect('core:checkout')

                return redirect('core:checkout')
            messages.warning(self.request, "Failed checkout")
            return redirect('core:checkout')
        except ObjectDoesNotExist:
            messages.error(
                self.request, "You do not have any items in the cart")
            return redirect("core:order-summary")
        # print(self.request.POST)


class PaymentView(View):
    def get(self, *args, **kwargs):
        # order
        order = Order.objects.get(user=self.request.user, ordered=False)
        context = {
            'order': order,
        }
        return render(self.request, "payment.html", context)

    def post(self, *args, **kwargs):
        # `source` is obtained with Stripe.js; see https://stripe.com/docs/payments/accept-a-payment-charges#web-create-token
        order = Order.objects.get(user=self.request.user, ordered=False)
        token = self.request.POST.get('stripeToken')
        amount = int(order.get_total() * 100)

        try:
            # Use Stripe's library to make requests...
            charge = stripe.Charge.create(
                amount=amount,  # in cents
                currency="usd",
                source=token,
                # description="My First Test Charge (created for API docs)",
            )

            order.ordered = True
            # create payment
            payment = Payment()
            payment.stripe_charge_id = charge['id']
            payment.user = self.request.user
            payment.amount = order.get_total()
            payment.save()

            # assign payment to order

            order.ordered = True
            order.payment = payment
            order.save()
            # error handling
            messages.success(self.request, "Your order was successful!")
            return redirect("/")

        except stripe.error.CardError as e:
            # Since it's a decline, stripe.error.CardError will be caught
            body = e.json_body
            err = body.get('error', {})
            messages.error(self.request, f"{err.get('message')}")
            return redirect("/")
        except stripe.error.RateLimitError as e:
            # Too many requests made to the API too quickly
            messages.error(self.request, "Rate limit error")
            return redirect("/")
        except stripe.error.InvalidRequestError as e:
            # Invalid parameters were supplied to Stripe's API
            messages.error(self.request, "Invalid parameters")
            return redirect("/")
        except stripe.error.AuthenticationError as e:
            # Authentication with Stripe's API failed
            # (maybe you changed API keys recently)
            messages.error(self.request, "Not authenticated")
            return redirect("/")
        except stripe.error.APIConnectionError as e:
            # Network communication with Stripe failed
            messages.error(self.request, "Network error")
            return redirect("/")
        except stripe.error.StripeError as e:
            # Display a very generic error to the user, and maybe send
            # yourself an email
            messages.error(self.request, "Something went wrong. You were not charged. Please try again")
            return redirect("/")
        except Exception as e:
            # Something else happened, completely unrelated to Stripe
            messages.error(self.request, "A serious error has occurred")
            return redirect("/")
            # Usually Code error


@login_required
def add_to_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    # avoid recreating the item to declutter log
    order_item, created = OrderItem.objects.get_or_create(
        item=item, user=request.user, ordered=False)
    # Only take the uncompleted order
    order_qs = Order.objects.filter(user=request.user, ordered=False)
    if order_qs.exists():
        order = order_qs[0]
        # see if the order item is in the order
        if order.items.filter(item__slug=item.slug).exists():
            order_item.quantity += 1
            order_item.save()
            messages.info(request, "The item quantity has been updated.")
            return redirect("core:order-summary")
        else:
            # Adding different tokens
            messages.info(request, "This item was added to your cart.")
            order.items.add(order_item)
            return redirect("core:order-summary")
    else:
        # New Order
        ordered_date = timezone.now()
        order = Order.objects.create(
            user=request.user, ordered_date=ordered_date)
        order.items.add(order_item)
        messages.info(request, "This item was added to your cart.")
        return redirect("core:order-summary")


@login_required
def remove_single_from_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order_qs = Order.objects.filter(
        user=request.user, ordered=False)
    if order_qs.exists():
        order = order_qs[0]
        # see if the order item is in the order
        if order.items.filter(item__slug=item.slug).exists():
            order_item = OrderItem.objects.filter(
                item=item, user=request.user, ordered=False)[0]
            if order_item.quantity > 1:
                order_item.quantity -= 1
            else:
                order.items.remove(order_item)
                order_item.delete()
            order_item.save()

            messages.info(request, "The item quantity has been updated.")
            return redirect("core:order-summary")
        else:
            # User does not contain does item
            messages.info(request, "This item is not in your cart.")
            return redirect("core:Product", slug=slug)
    else:
        # User has no orders
        messages.info(request, "There are no items in your cart.")
        return redirect("core:Product", slug=slug)


@login_required
def remove_from_cart(request, slug):
    item = get_object_or_404(Item, slug=slug)
    order_qs = Order.objects.filter(
        user=request.user, ordered=False)
    if order_qs.exists():
        order = order_qs[0]
        # see if the order item is in the order
        if order.items.filter(item__slug=item.slug).exists():
            order_item = OrderItem.objects.filter(
                item=item, user=request.user, ordered=False)[0]
            order.items.remove(order_item)
            # Remove the object - or else it will think it has 1
            order_item.delete()
            messages.info(request, "This item was removed from your cart.")
            return redirect("core:order-summary")
        else:
            # User does not contain does item
            messages.info(request, "This item is not in your cart.")
            return redirect("core:Product", slug=slug)
    else:
        # User has no orders
        messages.info(request, "There are no items in your cart.")
        return redirect("core:Product", slug=slug)


""" from django.shortcuts import render
from django.views.generic import ListView, DetailView
from .models import Item, OrderItem, Order

# Create your views here.


class HomeView(ListView):
    model = Item
    paginate_by = 10
    template_name = "home-page.html"


def products(request):
    context = {
        'items': Item.objects.all()
    }
    return render(request, "product-page.html", context)


class ItemView(DetailView):
    model = Item
    template_name = "product-page.html"
"""
