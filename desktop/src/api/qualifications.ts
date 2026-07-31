import { request } from './client'
import type {
  CertificateInput,
  CompanyInput,
  CompanyProfile,
  ExpiryWarnings,
  PaginatedData,
  PerformanceInput,
  PerformanceRecord,
  PersonnelCertificate,
  PersonnelInput,
  QualificationCertificate,
  QualificationImportResult,
} from '@/types/qualification'

const BASE = '/api/v1/qualifications'

export const qualificationApi = {
  expiryWarnings: () =>
    request<ExpiryWarnings>({ method: 'GET', url: `${BASE}/expiry-warnings` }),

  listCertificates: (params: { name?: string; status?: string; is_valid?: boolean } = {}) =>
    request<PaginatedData<QualificationCertificate>>({
      method: 'GET',
      url: `${BASE}/certificates`,
      params: { page: 1, page_size: 100, ...params },
    }),
  createCertificate: (payload: CertificateInput) =>
    request<QualificationCertificate>({
      method: 'POST',
      url: `${BASE}/certificates`,
      data: payload,
    }),
  updateCertificate: (id: string, payload: Partial<CertificateInput>) =>
    request<QualificationCertificate>({
      method: 'PUT',
      url: `${BASE}/certificates/${id}`,
      data: payload,
    }),
  removeCertificate: (id: string) =>
    request<{ id: string; deleted: boolean }>({
      method: 'DELETE',
      url: `${BASE}/certificates/${id}`,
    }),

  listPerformances: (params: { keyword?: string; is_completed?: boolean } = {}) =>
    request<PaginatedData<PerformanceRecord>>({
      method: 'GET',
      url: `${BASE}/performances`,
      params: { page: 1, page_size: 100, ...params },
    }),
  createPerformance: (payload: PerformanceInput) =>
    request<PerformanceRecord>({
      method: 'POST',
      url: `${BASE}/performances`,
      data: payload,
    }),
  updatePerformance: (id: string, payload: Partial<PerformanceInput>) =>
    request<PerformanceRecord>({
      method: 'PUT',
      url: `${BASE}/performances/${id}`,
      data: payload,
    }),
  removePerformance: (id: string) =>
    request<{ id: string; deleted: boolean }>({
      method: 'DELETE',
      url: `${BASE}/performances/${id}`,
    }),

  listPersonnel: (params: { person_name?: string; is_on_job?: boolean; is_valid?: boolean } = {}) =>
    request<PaginatedData<PersonnelCertificate>>({
      method: 'GET',
      url: `${BASE}/personnel`,
      params: { page: 1, page_size: 100, ...params },
    }),
  createPersonnel: (payload: PersonnelInput) =>
    request<PersonnelCertificate>({
      method: 'POST',
      url: `${BASE}/personnel`,
      data: payload,
    }),
  updatePersonnel: (id: string, payload: Partial<PersonnelInput>) =>
    request<PersonnelCertificate>({
      method: 'PUT',
      url: `${BASE}/personnel/${id}`,
      data: payload,
    }),
  removePersonnel: (id: string) =>
    request<{ id: string; deleted: boolean }>({
      method: 'DELETE',
      url: `${BASE}/personnel/${id}`,
    }),

  listCompanies: (params: { company_name?: string } = {}) =>
    request<PaginatedData<CompanyProfile>>({
      method: 'GET',
      url: `${BASE}/company`,
      params: { page: 1, page_size: 100, ...params },
    }),
  createCompany: (payload: CompanyInput) =>
    request<CompanyProfile>({
      method: 'POST',
      url: `${BASE}/company`,
      data: payload,
    }),
  updateCompany: (id: string, payload: Partial<CompanyInput>) =>
    request<CompanyProfile>({
      method: 'PUT',
      url: `${BASE}/company/${id}`,
      data: payload,
    }),
  removeCompany: (id: string) =>
    request<{ id: string; deleted: boolean }>({
      method: 'DELETE',
      url: `${BASE}/company/${id}`,
    }),

  importExcel: (file: File) => {
    const formData = new FormData()
    formData.append('file', file)
    return request<QualificationImportResult>({
      method: 'POST',
      url: `${BASE}/import`,
      data: formData,
      timeout: 5 * 60 * 1000,
    })
  },
}
