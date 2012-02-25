from django.shortcuts import render_to_response
from django.template import RequestContext
from django.contrib.auth.decorators import login_required
from django.contrib.auth.models import User
from django.core.context_processors import csrf
from datetime import datetime

from people.forms import *
from people.models import *
from django.core.files.uploadedfile import SimpleUploadedFile

@login_required
def list_all(request):
    """ List all users in the system. (Alphabetically, ignoring case)
    """
    users = User.objects.filter(is_active=True).extra(select={'username_upper': 'upper(username)'}, order_by=['username_upper'])
    return render_to_response('list.html', locals(), context_instance=RequestContext(request))

@login_required
def view_profile(request, name):
    """ Show a user profile.
    """

    this_user = User.objects.get(username=name)
    if UserProfile.objects.filter(user=this_user): 
        #User has already created a user profile.
        profile = UserProfile.objects.get(user=this_user)

        if request.user.__str__() == name or request.user.is_superuser:
            edit = True

        return render_to_response('profile.html', locals())
    else:
        #User HAS NOT created a user profile, allow them to create one.
        return create_user_profile(request,name)

@login_required
def create_user_profile(request,name):
    """ This view is called when creating or editing a user profile to the system.
        Allows the user to edit and display certain things about their information.
    """
    c = {}
    c.update(csrf(request))

    if request.user.__str__() != name and not request.user.is_superuser:
        # Don't allow editing of other people's profiles.
        return render_to_response('not_your_profile.html',locals(),context_instance=RequestContext(request))

    #Grab the user that the name belongs to and check to see if they have an existing profile.
    user = User.objects.get(username=name)
    try:
        profile = UserProfile.objects.get(user=user)
    except UserProfile.DoesNotExist:
        profile = None

    if request.method == 'POST':
        form = CreateUserProfileForm(request.POST,request.FILES,instance=profile)
        if form.is_valid():
            if profile:
                # Update the user profile
                profile = form.save()
            else:
                # Create a user profile, but DON'T add to database quite yet.
                profile = form.save(commit=False)

                # Add user to the profile and save
                profile.user = user
                profile.save()

                # Now, save the many-to-many data for the form (Required when commit=False)
                form.save_m2m()

            # Allow editing right after creating/editing a profile.
            edit = True
            # View the profile
            return render_to_response('profile.html',locals(),context_instance=RequestContext(request))
    else:
        form = CreateUserProfileForm(instance=profile)

    # Differentiate between a super user creating a profile or a person creating their own profile.
    this_user = request.user
    if profile:
        message = "You are editing a user profile for "
    else:
        message = "You are creating a user profile for "

    if this_user.__str__() == name:
        message += "yourself."
    else:
        message += name + "."

    return render_to_response('create_profile.html',locals(),context_instance=RequestContext(request))

@login_required
def view_and_edit_reviews(request,user):

    # Grab the user and any reviews they may have. 
    user = User.objects.get(username=user)
    this_user = request.user
    if this_user.has_perm('people.add_uwltreview'):
        can_add_review = True
    else:
        can_add_review = False

    if not can_add_review and this_user != user:
        return render_to_response('fail.html',locals(),context_instance=RequestContext(request))

    # TODO: Try to not use the is_superuser permission, instead maybe use a group permission.
    if this_user.is_superuser:
        final_reviewer = True
    else:
        final_reviewer = False

    try:
        badge_photo = UserProfile.objects.get(user=user).bagde_photo._get_url()
    except:
        badge_photo = None

    try:
        reviews = UWLTReview.objects.filter(user=user)
    except UWLTReview.DoesNotExist:
        reviews = None

    # Gather the data from the reviews and separate out fields.    
    sorted_review_list = []
    recent_review = None
    for review in reviews:
        
        scores = {
            'Teamwork': review.teamwork,
            'Customer service': review.customer_service,
            'Dependability': review.dependability,
            'Integrity': review.integrity,
            'Communication': review.communication,
            'Initiative': review.initiative,
            'Attitude': review.attitude,
            'Productivity': review.productivity,
            'Technical knowledge': review.technical_knowledge,
            'Responsibility': review.responsibility,
            'Policies': review.policies,
            'Procedures': review.procedures,
        }
        comments = review.comments
        date = review.date
        sorted_review_list.append({'user':user, 'date':review.date, 'scores': scores, 'comments':comments})
        if review.reviewer == this_user:
            recent_review = review

    # Handle the form submission and differentiate between the sub-reviewers and the final reviewer. 
    if request.method == 'POST':
        
        if final_reviewer:
            form = CreateFinalUWLTReviewForm(request.POST, instance=recent_review)
        else:
            form = CreateUWLTReviewForm(request.POST, instance=recent_review)

        if form.is_valid:
            review = form.save(commit=False)
            review.user = user
            review.date = datetime.now().date()
            review.reviewer = this_user
            review.is_used_up = False
            review.is_final = False
            review.save()
            form.save_m2m()
    else:
        if final_reviewer:
            form = CreateFinalUWLTReviewForm(request.POST, instance = recent_review)
        else:
            form = CreateUWLTReviewForm(instance=recent_review)

    # Notify the user of a previous review.
    recent_message = ''
    if recent_review:
        recent_message = 'Looks like you made a review for %s on %s. Saved entries have been filled out.' % (user,recent_review.date)

    args = {
        'request': request,
        'form': form,
        'reviews': sorted_review_list,
        'this_user': this_user,
        'user': user,
        'badge_photo': badge_photo,
        'can_add_review': can_add_review,
        'recent_message': recent_message,
    }
    return render_to_response('reviews.html', args, context_instance=RequestContext(request))

