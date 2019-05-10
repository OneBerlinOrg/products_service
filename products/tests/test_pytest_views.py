import uuid

import pytest
from django.core.files.uploadedfile import SimpleUploadedFile
from django.urls import reverse
from moto import mock_s3

from . import model_factories
from ..views import ProductViewSet
from ..models import Product
from .fixtures import user, products, product_with_file, TEST_TYPE, TEST_WF2, TEST_ORGANIZATION


@pytest.mark.django_db()
class TestProductsBase(object):
    organization_uuid = TEST_ORGANIZATION
    session = {
        'jwt_organization_uuid': organization_uuid,
    }


class TestProductsList(TestProductsBase):

    def test_products_list_empty(self, api_rf, user):
        request = api_rf.get(reverse('product-list'))
        request.user = user
        request.session = self.session
        response = ProductViewSet.as_view({'get': 'list'})(request)
        assert response.status_code == 200
        assert response.data['results'] == []

    def test_products_list(self, api_rf, user, products):
        request = api_rf.get(reverse('product-list'))
        request.user = user
        request.session = self.session
        response = ProductViewSet.as_view({'get': 'list'})(request)
        assert response.status_code == 200
        assert len(response.data['results']) == 3

        product_data = response.data['results'][0]
        assert 'uuid' in product_data
        assert 'name' in product_data

    def test_products_list_with_name_filter(self, api_rf, user, products):
        request = api_rf.get('{}?type={}'.format(reverse('product-list'),
                                                 TEST_TYPE))
        request.user = user
        request.session = self.session
        response = ProductViewSet.as_view({'get': 'list'})(request)
        assert response.status_code == 200
        assert len(response.data['results']) == 1

        product_data = response.data['results'][0]
        assert 'uuid' in product_data
        assert 'name' in product_data
        assert 'type' in product_data
        assert product_data['type'] == TEST_TYPE

    def test_products_list_with_wf2_filter(self, api_rf, user, products):
        request = api_rf.get('{}?workflowlevel2_uuid={}'.format(
            reverse('product-list'), TEST_WF2)
        )
        request.user = user
        request.session = self.session
        response = ProductViewSet.as_view({'get': 'list'})(request)
        assert response.status_code == 200
        assert len(response.data['results']) == 1

        product_data = response.data['results'][0]
        assert 'uuid' in product_data
        assert 'name' in product_data
        assert 'workflowlevel2_uuid' in product_data
        assert product_data['workflowlevel2_uuid'] == TEST_WF2

    def test_products_list_with_several_wf2_filter(self, api_rf, user, products):
        test_wf22 = str(uuid.uuid4())
        model_factories.ProductFactory.create(
            workflowlevel2_uuid=test_wf22,
            organization_uuid=TEST_ORGANIZATION,
        )
        request = api_rf.get(f'{format(reverse("product-list"))}?workflowlevel2_uuid={TEST_WF2},{test_wf22}')
        request.user = user
        request.session = self.session
        response = ProductViewSet.as_view({'get': 'list'})(request)
        assert response.status_code == 200
        assert len(response.data['results']) == 2

        product_data = response.data['results'][0]
        assert 'uuid' in product_data
        assert 'name' in product_data
        assert 'workflowlevel2_uuid' in product_data
        assert product_data['workflowlevel2_uuid'] in (TEST_WF2, test_wf22)
        assert response.data['results'][1]['workflowlevel2_uuid'] in (TEST_WF2, test_wf22)
        assert response.data['results'][1]['workflowlevel2_uuid'] != response.data['results'][0]['workflowlevel2_uuid']

    def test_products_empty_filter(self, api_rf, user, products):
        request = api_rf.get('{}?type={}'.format(reverse('product-list'),
                                                 'nonexistent'))
        request.user = user
        request.session = self.session
        response = ProductViewSet.as_view({'get': 'list'})(request)
        assert response.status_code == 200
        assert len(response.data['results']) == 0

        request = api_rf.get('{}?workflowlevel2_uuid={}'.format(
            reverse('product-list'), 'nonexistent')
        )
        request.user = user
        request.session = self.session
        response = ProductViewSet.as_view({'get': 'list'})(request)
        assert response.status_code == 200
        assert len(response.data['results']) == 0


class TestProductsDetail(TestProductsBase):

    def test_product_detail(self, api_rf, user):
        product = model_factories.ProductFactory.create(
            organization_uuid=TEST_ORGANIZATION
        )

        request = api_rf.get(reverse('product-detail',
                                     args=(product.uuid,)))
        request.user = user
        request.session = self.session
        response = ProductViewSet.as_view({'get': 'retrieve'})(request,  uuid=str(product.uuid))  # noqa
        assert response.status_code == 200
        assert response.data

        assert response.data['uuid'] == str(product.pk)
        assert response.data['uuid'] == str(product.uuid)
        assert 'name' in response.data
        assert 'workflowlevel2_uuid' in response.data

    def test_nonexistent_product(self, api_rf, user):
        request = api_rf.get(reverse('product-detail', args=(222,)))
        request.user = user
        request.session = self.session
        response = ProductViewSet.as_view({'get': 'retrieve'})(request, uuid='e70d4613-2055-4c95-9815-ea2f07210d55')  # noqa
        assert response.status_code == 404

    def test_product_with_file_detail(self, api_rf, user, product_with_file):
        request = api_rf.get(reverse('product-detail',
                                     args=(product_with_file.uuid,)))
        request.user = user
        request.session = self.session
        response = ProductViewSet.as_view({'get': 'retrieve'})(
            request,  uuid=str(product_with_file.uuid)
        )
        assert response.status_code == 200
        assert response.data
        assert response.data['file'] == reverse('product-file',
                                                args=(product_with_file.uuid,))
        assert response.data['file_name'] == product_with_file.file_name


@mock_s3
class TestProductsCreate(TestProductsBase):

    def test_create_product_with_file(self, api_rf, user, s3_conn):
        file_mock = SimpleUploadedFile('foo.pdf', b'some content',
                                       content_type='multipart/form-data')
        data = {
            'workflowlevel2_uuid': str(uuid.uuid4()),
            'name': 'Test name',
            'file': file_mock,
            'file_name': 'bar.pdf',
        }
        request = api_rf.post(reverse('product-list'), data)
        request.user = user
        request.session = self.session
        response = ProductViewSet.as_view({'post': 'create'})(request)
        assert response.status_code == 201

        product = Product.objects.get(uuid=response.data['uuid'])
        assert product.file
        assert product.file_name == 'bar.pdf'
        assert response.data['file'] == reverse('product-file',
                                                args=(product.uuid,))

    def test_create_product_with_file_without_name(self, api_rf, user,
                                                   s3_conn):
        file_mock = SimpleUploadedFile('foo.pdf', b'some content',
                                       content_type='multipart/form-data')
        data = {
            'workflowlevel2_uuid': str(uuid.uuid4()),
            'name': 'Test name',
            'file': file_mock,
        }
        request = api_rf.post(reverse('product-list'), data)
        request.user = user
        request.session = self.session
        response = ProductViewSet.as_view({'post': 'create'})(request)
        assert response.status_code == 201

        product = Product.objects.get(uuid=response.data['uuid'])
        assert product.file
        assert product.file_name == 'foo.pdf'


@mock_s3
class TestProductsUpdate(TestProductsBase):

    def test_create_product_with_file(self, api_rf, user, s3_conn):
        file_mock = SimpleUploadedFile('foo.pdf', b'some content',
                                       content_type='multipart/form-data')
        data = {
            'workflowlevel2_uuid': str(uuid.uuid4()),
            'name': 'Test name',
            'file': file_mock,
            'file_name': 'bar.pdf',
        }
        request = api_rf.post(reverse('product-list'), data)
        request.user = user
        request.session = self.session
        response = ProductViewSet.as_view({'post': 'create'})(request)
        assert response.status_code == 201

        product = Product.objects.get(uuid=response.data['uuid'])
        assert product.file
        assert product.file_name == 'bar.pdf'
        assert response.data['file'] == reverse('product-file',
                                                args=(product.uuid,))


@mock_s3
class TestProductFile(TestProductsBase):

    def test_product_file(self, api_rf, user, product_with_file):
        request = api_rf.get(reverse('product-file',
                                     args=(product_with_file.uuid,)))
        request.user = user
        request.session = self.session
        response = ProductViewSet.as_view({'get': 'file'})(
            request, uuid=product_with_file.uuid
        )
        assert response.status_code == 200
        assert response['Content-Disposition'] == 'attachment; filename={}'\
            .format(product_with_file.file_name)
