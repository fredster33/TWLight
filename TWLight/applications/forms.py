"""
This forms.py contains base forms that applications/views.py will use to
generate the actual forms filled in by users in making requests for partner
content.

For usability reasons, we only want users to have to fill in one form at a time
(even if they are requesting access to multiple partners' resources), and we
only want to ask them once for any piece of data even if multiple partners
require it, and we *don't* want to ask them for data that *isn't* required by
any of the partners in their set.

This means that the actual form we present to users must be generated
dynamically; we cannot hardcode it here. What we have here instead is a base
form that takes a dict of required fields, and constructs the form accordingly.
(See the docstring of BaseApplicationForm for the expected dict format.)
"""

from crispy_forms.helper import FormHelper
from crispy_forms.layout import Layout, Fieldset, Submit
import logging
import re

from django import forms
from django.utils.translation import ugettext as _

from TWLight.applications.helpers import (USER_FORM_FIELDS,
                                          PARTNER_FORM_OPTIONAL_FIELDS,
                                          PARTNER_FORM_BASE_FIELDS,
                                          FIELD_TYPES,
                                          FIELD_LABELS)
from TWLight.resources.models import Partner


logger = logging.getLogger(__name__)


class BaseApplicationForm(forms.Form):
    """
    Given a dict of parameters describing the required fields for this
    application, constructs a suitable application form.

    Expected dict format:
        {
            'user': [list, of, required, user, data, fields],
            'partner_1': [list, of, required, fields, for, partner, 1],
            'partner_2': [list, of, required, fields, for, partner, 2],
            (additional partners as needed)
        }

    'user' is mandatory. 'partner_1' is mandatory. Additional partners are
    optional.

    See https://django-crispy-forms.readthedocs.org/ for information on form
    layout.
    """

    def __init__(self, *args, **kwargs):
        self._validate_parameters(**kwargs)
        self.field_params = kwargs.pop('field_params')

        super(BaseApplicationForm, self).__init__(*args, **kwargs)

        # TODO: form layout for RTL
        # TODO: figure out how to activate translation & localization for
        # form error messages
        self.helper = FormHelper()
        self._initialize_form_helper()

        self.helper.layout = Layout()

        user_data = self.field_params.pop('user')
        self._add_user_data_subform(user_data)

        # For each partner, build a partner data section of the form.
        for partner in self.field_params:
            self._add_partner_data_subform(partner)

        self.helper.add_input(Submit(
            'submit',
            _('Submit application'),
            css_class='center-block'))


    def _get_partner_object(self, partner):
        # Extract the number component of (e.g.) 'partner_1'.
        try:
            partner_id = partner[8:]

            # Verify that it is the ID number of a real partner.
            partner = Partner.objects.get(id=partner_id)

            return partner
        except Partner.DoesNotExist:
            logger.exception('BaseApplicationForm received a partner ID that '
                'did not match any partner in the database')
            raise


    def _validate_parameters(self, **kwargs):
        """
        Ensure that parameters have been passed in and match the format
        specified in the docstring.
        """
        try:
            field_params = kwargs['field_params']
        except KeyError:
            logger.exception('Tried to instantiate a BaseApplicationForm but '
                'did not have field_params')
            raise

        try:
            assert 'user' in field_params
        except AssertionError:
            logger.exception('Tried to instantiate a BaseApplicationForm but '
                'there was no user parameter in field_params')
            raise

        try:
            # We should have 'user' plus at least one partner in the keys.
            assert len(field_params.keys()) >= 2
        except AssertionError:
            logger.exception('Tried to instantiate a BaseApplicationForm but '
                'there was not enough information in field_params')
            raise

        expected = re.compile(r'partner_\d+')

        for key in field_params.keys():
            # All keys which are not the user data should be partner data.
            if key != 'user':
                try:
                    assert expected.match(key)
                except AssertionError:
                    logger.exception('Tried to instantiate a BaseApplicationForm but '
                        'there was a key that did not match any expected values')


    def _validate_user_data(self, user_data):
        try:
            assert (set(user_data) <= set(USER_FORM_FIELDS))
        except AssertionError:
            logger.exception('BaseApplicationForm received invalid user data')
            raise


    def _validate_partner_data(self, partner_data):
        try:
            assert (set(partner_data) <= set(PARTNER_FORM_OPTIONAL_FIELDS))

        except AssertionError:
            logger.exception('BaseApplicationForm received invalid partner data')
            raise


    def _initialize_form_helper(self):
        # Add basic styling to the form.
        self.helper.form_class = 'form-horizontal'
        self.helper.label_class = 'col-xs-12 col-sm-4 col-md-3'
        self.helper.field_class = 'col-xs-12 col-sm-8 col-md-9'


    def _add_user_data_subform(self, user_data):
        self._validate_user_data(user_data)

        user_data_layout = Fieldset(_('Information about you'))
        for datum in user_data:
            self.fields[datum] = FIELD_TYPES[datum]
            self.fields[datum].label = FIELD_LABELS[datum]
            user_data_layout.append(datum)
        self.helper.layout.append(user_data_layout)


    def _add_partner_data_subform(self, partner):
        partner_data = self.field_params[partner]
        partner_object = self._get_partner_object(partner)
        partner_layout = Fieldset(
            _('Your application to {partner}').format(partner=partner_object))

        self._validate_partner_data(partner_data)

        # partner_data lists the optional fields required by that partner;
        # base fields should be in the form for all partners.
        all_partner_data = partner_data + PARTNER_FORM_BASE_FIELDS

        for datum in all_partner_data:
            # This will yield fields with names like 'partner_1_occupation'.
            # This will let us tell during form processing which fields
            # belong to which partners.
            field_name = '{partner}_{datum}'.format(
                partner=partner, datum=datum)
            self.fields[field_name] = FIELD_TYPES[datum]
            self.fields[field_name].label = FIELD_LABELS[datum]
            partner_layout.append(field_name)

        self.helper.layout.append(partner_layout)
