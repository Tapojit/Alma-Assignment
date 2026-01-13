from pydantic import BaseModel, Field
from typing import Optional


class FormA28Data(BaseModel):
    """Complete structured data for Form A-28 from all documents"""

    # Part 1: Attorney/Representative Information
    attorney_online_account: Optional[str] = Field(
        None, description="USCIS Online Account Number")
    attorney_family_name: Optional[str] = Field(
        None, description="Attorney's last name")
    attorney_given_name: Optional[str] = Field(
        None, description="Attorney's first name")
    attorney_middle_name: Optional[str] = Field(
        None, description="Attorney's middle name")
    attorney_street_number: Optional[str] = Field(
        None, description="Street number and name")
    attorney_apt_ste_flr: Optional[str] = Field(
        None, description="Apartment, Suite, or Floor number")
    attorney_city: Optional[str] = Field(None, description="City or Town")
    attorney_state: Optional[str] = Field(
        None, description="State (use abbreviation)")
    attorney_zip_code: Optional[str] = Field(None, description="ZIP Code")
    attorney_country: Optional[str] = Field(None, description="Country")
    attorney_daytime_phone: Optional[str] = Field(
        None, description="Daytime Telephone Number")
    attorney_mobile_phone: Optional[str] = Field(
        None, description="Mobile Telephone Number")
    attorney_email: Optional[str] = Field(None, description="Email Address")
    attorney_fax_number: Optional[str] = Field(None, description="Fax Number")

    # Part 2: Eligibility Information
    attorney_licensing_authority: Optional[str] = Field(
        None, description="State/jurisdiction where licensed")
    attorney_bar_number: Optional[str] = Field(None, description="Bar Number")
    attorney_subject_to_restrictions: Optional[str] = Field(
        None, description="Whether subject to restrictions (am or am not)")
    attorney_law_firm: Optional[str] = Field(
        None, description="Name of Law Firm or Organization")
    attorney_recognized_org: Optional[str] = Field(
        None, description="Name of Recognized Organization")
    attorney_accreditation_date: Optional[str] = Field(
        None, description="Date of Accreditation (MM/DD/YYYY)")

    # Part 3: Passport/Beneficiary Information (from passport document)
    beneficiary_last_name: Optional[str] = Field(
        None, description="Last name from passport")
    beneficiary_first_name: Optional[str] = Field(
        None, description="First name(s) from passport")
    beneficiary_middle_name: Optional[str] = Field(
        None, description="Middle name(s) from passport")
    passport_number: Optional[str] = Field(None, description="Passport number")
    passport_country_of_issue: Optional[str] = Field(
        None, description="Country that issued passport")
    passport_nationality: Optional[str] = Field(
        None, description="Nationality")
    beneficiary_date_of_birth: Optional[str] = Field(
        None, description="Date of birth (MM/DD/YYYY)")
    beneficiary_place_of_birth: Optional[str] = Field(
        None, description="Place/city of birth")
    beneficiary_sex: Optional[str] = Field(
        None, description="Sex (M, F, or X)")
    passport_date_of_issue: Optional[str] = Field(
        None, description="Passport issue date (MM/DD/YYYY)")
    passport_date_of_expiration: Optional[str] = Field(
        None, description="Passport expiration date (MM/DD/YYYY)")

    # Part 4: Client Information (from G-28 form)
    client_family_name: Optional[str] = Field(
        None, description="Client's last name")
    client_given_name: Optional[str] = Field(
        None, description="Client's first name")
    client_middle_name: Optional[str] = Field(
        None, description="Client's middle name")
    client_daytime_phone: Optional[str] = Field(
        None, description="Client's daytime telephone")
    client_mobile_phone: Optional[str] = Field(
        None, description="Client's mobile telephone")
    client_email: Optional[str] = Field(
        None, description="Client's email address")
    client_street_number: Optional[str] = Field(
        None, description="Client's street address")
    client_apt_ste_flr: Optional[str] = Field(
        None, description="Client's apartment/suite/floor")
    client_city: Optional[str] = Field(None, description="Client's city")
    client_state: Optional[str] = Field(
        None, description="Client's state or province")
    client_zip_code: Optional[str] = Field(
        None, description="Client's ZIP Code (US) or Postal Code (international)")
    client_country: Optional[str] = Field(None, description="Client's country")
    client_uscis_account: Optional[str] = Field(
        None, description="Client's USCIS Online Account Number")
    client_alien_number: Optional[str] = Field(
        None, description="Client's A-Number (Alien Registration Number)")
