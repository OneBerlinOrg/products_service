import json
import uuid

from django.test import TestCase
from rest_framework.test import APIRequestFactory

from . import model_factories
from ..views import ProductViewSet, PropertyViewSet, ProductCategoryViewSet
from ..models import Product, Property, Category


class ProductViewsBaseTest(TestCase):

    def setUp(self):
        self.factory = APIRequestFactory()
        self.user = model_factories.User()
        self.organization_uuid = str(uuid.uuid4())
        self.session = {
            'jwt_organization_uuid': self.organization_uuid,
        }


class ProductListTest(ProductViewsBaseTest):

    def test_list_products_pagination_limit(self):
        model_factories.ProductFactory.create_batch(
            size=51, organization_uuid=self.organization_uuid)
        request = self.factory.get('')
        request.user = self.user
        request.session = self.session
        view = ProductViewSet.as_view({'get': 'list'})
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 50)
        self.assertEqual(response.data['next'], 'http://testserver/?limit=50&offset=50')

    def test_fail_read_other_organization_products(self):
        model_factories.ProductFactory.create()
        request = self.factory.get('')
        request.user = self.user
        request.session = self.session
        view = ProductViewSet.as_view({'get': 'list'})
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data['results']), 0)


class ProductCreateTest(ProductViewsBaseTest):

    def test_create_product(self):
        data = {
            'workflowlevel2_uuid': str(uuid.uuid4()),
            'name': 'Test name',
            'make': 'Test company',
            'type': 'Test type',
            'description': 'Foo bar foo bar',
            'status': 'in-stock',
        }
        request = self.factory.post('', data)
        request.user = self.user
        request.session = self.session
        response = ProductViewSet.as_view(
            {'post': 'create'}
        )(request).render()

        self.assertEqual(response.status_code, 201)

        product = Product.objects.get(uuid=response.data['uuid'])
        self.assertEqual(product.workflowlevel2_uuid,
                         data['workflowlevel2_uuid'])
        self.assertEqual(product.name, data['name'])
        self.assertEqual(product.make, data['make'])
        self.assertEqual(product.type, data['type'])
        self.assertEqual(product.description, data['description'])
        self.assertEqual(product.status, data['status'])
        self.assertEqual(str(product.organization_uuid), self.organization_uuid)

    def test_create_product_fail(self):
        data = {
            'workflowlevel2_uuid': str(uuid.uuid4()),
            'name': '',
        }
        request = self.factory.post('', data)
        request.user = self.user
        request.session = self.session
        response = ProductViewSet.as_view({'post': 'create'})(request)
        self.assertEqual(response.status_code, 400)


class ProductUpdateTest(ProductViewsBaseTest):

    def test_update_product(self):
        product = model_factories.ProductFactory.create(
            organization_uuid=self.organization_uuid,
        )
        data = {
            'workflowlevel2_uuid': str(uuid.uuid4()),  # changing
            'name': 'New name',  # changing
            'make': product.make,
            'model': product.model,
            'type': product.type,
            'status': product.status,
        }
        request = self.factory.put('', data)
        request.user = self.user
        request.session = self.session
        response = ProductViewSet.as_view({'put': 'update'})(request,
                                                             uuid=product.uuid)
        self.assertEqual(response.status_code, 200)

        product = Product.objects.get(uuid=response.data['uuid'])
        self.assertEqual(product.workflowlevel2_uuid,
                         data['workflowlevel2_uuid'])
        self.assertEqual(product.name, data['name'])

    def test_fail_update_other_organization_product(self):
        product = model_factories.ProductFactory.create()
        data = {'anything': 'doesn`t matter'}
        request = self.factory.put('', data)
        request.user = self.user
        request.session = self.session
        response = ProductViewSet.as_view(
            {'put': 'update'})(request, uuid=product.uuid)
        self.assertEqual(response.status_code, 404)

    def test_update_product_replacement(self):
        product1 = model_factories.ProductFactory.create(
            organization_uuid=self.organization_uuid)
        product2 = model_factories.ProductFactory.create(
            organization_uuid=self.organization_uuid)
        data = {
            'workflowlevel2_uuid': str(uuid.uuid4()),  # changing
            'name': 'New name',  # changing
            'make': product1.make,
            'model': product1.model,
            'type': product1.type,
            'status': product1.status,
            'replacement_product': product2.uuid,
        }
        request = self.factory.put('', data)
        request.user = self.user
        request.session = self.session
        response = ProductViewSet.as_view({'put': 'update'})(request, uuid=product1.uuid)
        self.assertEqual(response.status_code, 200)

        product = Product.objects.get(uuid=response.data['uuid'])
        self.assertEqual(product.workflowlevel2_uuid, data['workflowlevel2_uuid'])
        self.assertEqual(product.name, data['name'])

        # test replaced_product
        product3 = model_factories.ProductFactory.create()
        data = {
            'name': 'New name',
            'replaced_product': product3.uuid,
        }
        request = self.factory.put('', data)
        request.user = self.user
        request.session = self.session
        response = ProductViewSet.as_view({'put': 'update'})(request,
                                                             uuid=product1.uuid)
        self.assertEqual(response.status_code, 200)

        product = Product.objects.get(uuid=response.data['uuid'])
        self.assertEqual(product.replaced_product, product3)
        product3 = Product.objects.get(uuid=product3.uuid)
        self.assertEqual(product3.replacement_product, product1)

    def test_remove_replaced_product(self):
        product1 = model_factories.ProductFactory.create(
            organization_uuid=self.organization_uuid)
        product2 = model_factories.ProductFactory.create(
            organization_uuid=self.organization_uuid)
        product2.replacement_product = product1
        product2.save()
        product1 = Product.objects.get(uuid=product1.uuid)
        self.assertEqual(product1.replaced_product, product2)

        data = {
            'name': 'required',
            'replaced_product': '',
        }
        request = self.factory.put('', data)
        request.user = self.user
        request.session = self.session
        response = ProductViewSet.as_view({'put': 'update'})(request, uuid=product1.uuid)
        self.assertEqual(response.status_code, 200)

        product1 = Product.objects.get(uuid=product1.uuid)
        self.assertEqual(product1.name, data['name'])
        self.assertFalse(hasattr(product1, 'replaced_product'))

    def test_remove_replacement_product(self):
        product1 = model_factories.ProductFactory.create(
            organization_uuid=self.organization_uuid)
        product2 = model_factories.ProductFactory.create(
            organization_uuid=self.organization_uuid)
        product1.replacement_product = product2
        product1.save()
        product1 = Product.objects.get(uuid=product1.uuid)
        self.assertEqual(product1.replacement_product, product2)

        data = {
            'name': 'required',
            'replacement_product': '',
        }
        request = self.factory.put('', data)
        request.user = self.user
        request.session = self.session
        response = ProductViewSet.as_view({'put': 'update'})(request, uuid=product1.uuid)
        self.assertEqual(response.status_code, 200)

        product1 = Product.objects.get(uuid=product1.uuid)
        self.assertEqual(product1.name, data['name'])
        self.assertIsNone(product1.replacement_product)

    def test_update_product_fail(self):
        product = model_factories.ProductFactory.create(
            organization_uuid=self.organization_uuid)
        data = {
            'name': '',
        }
        request = self.factory.put('', data)
        request.user = self.user
        request.session = self.session
        response = ProductViewSet.as_view({'put': 'update'})(request,
                                                             uuid=product.uuid)
        self.assertEqual(response.status_code, 400)


class ProductDeleteTest(ProductViewsBaseTest):

    def test_delete_product(self):
        product = model_factories.ProductFactory.create(
            organization_uuid=self.organization_uuid)
        self.assertEqual(1, Product.objects.count())
        request = self.factory.delete('')
        request.user = self.user
        request.session = self.session
        response = ProductViewSet.as_view(
            {'delete': 'destroy'})(request, uuid=product.uuid)
        self.assertEqual(response.status_code, 204)
        self.assertEqual(0, Product.objects.count())

    def test_fail_delete_other_organization_product(self):
        product = model_factories.ProductFactory.create()
        self.assertEqual(1, Product.objects.count())
        request = self.factory.delete('')
        request.user = self.user
        request.session = self.session
        response = ProductViewSet.as_view(
            {'delete': 'destroy'})(request, uuid=product.uuid)
        self.assertEqual(response.status_code, 404)
        self.assertEqual(1, Product.objects.count())


class PropertyListTest(ProductViewsBaseTest):

    def test_property_list(self):
        products = model_factories.ProductFactory.create_batch(2)

        prop1 = model_factories.PropertyFactory.create()
        prop2 = model_factories.PropertyFactory.create(products=products[:1])
        prop3 = model_factories.PropertyFactory.create(products=products)

        request = self.factory.get('')
        request.user = self.user
        response = PropertyViewSet.as_view({'get': 'list'})(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(response.data), 3)

        for prop_data in response.data:
            if prop_data['uuid'] == prop1.pk:
                self.assertEqual(prop_data['product'], [])
            elif prop_data['uuid'] == prop2.pk:
                self.assertEqual(len(prop_data['product']), 1)
            elif prop_data['uuid'] == prop3.pk:
                self.assertEqual(len(prop_data['product']), 2)

    def test_property_list_empty(self):
        request = self.factory.get('')
        request.user = self.user
        view = PropertyViewSet.as_view({'get': 'list'})
        response = view(request)
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data, [])


class PropertyDetailTest(ProductViewsBaseTest):

    def test_property_daetail(self):
        products = model_factories.ProductFactory.create_batch(2)
        prop = model_factories.PropertyFactory.create(products=products)

        request = self.factory.get('')
        request.user = self.user
        response = PropertyViewSet.as_view({'get': 'retrieve'})(request,
                                                                pk=prop.pk)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.data)


class PropertyCreateTest(ProductViewsBaseTest):

    def test_create_property(self):
        products = model_factories.ProductFactory.create_batch(2)
        data = {
            'name': 'Test name',
            'type': 'Test type',
            'value': '55',
            'product': [item.pk for item in products]
        }
        request = self.factory.post('', data)
        request.user = self.user
        response = PropertyViewSet.as_view({'post': 'create'})(request)
        self.assertEqual(response.status_code, 201)

        prop = Property.objects.get(pk=response.data['uuid'])
        self.assertEqual(prop.name, data['name'])
        self.assertEqual(prop.type, data['type'])
        self.assertEqual(prop.value, data['value'])
        self.assertCountEqual(prop.product.all(), products)

    def test_create_property_fail(self):
        data = {
            'name': '',  # 'name' is required
            'value': '',  # 'value' is required
        }
        request = self.factory.post('', data)
        request.user = self.user
        request.session = self.session
        response = ProductViewSet.as_view({'post': 'create'})(request)
        self.assertEqual(response.status_code, 400)


class PropertyUpdateTest(ProductViewsBaseTest):

    def test_update_property(self):
        products = model_factories.ProductFactory.create_batch(2)
        prop = model_factories.PropertyFactory.create(products=products)
        data = {
            'name': prop.name,
            'type': prop.type,
            'value': 'New value',  # change "value" field
            'product': [products[0].pk]
        }
        request = self.factory.put('', data)
        request.user = self.user
        response = PropertyViewSet.as_view({'put': 'update'})(request,
                                                              pk=prop.pk)
        self.assertEqual(response.status_code, 200)

        prop_updated = Property.objects.get(pk=response.data['uuid'])
        self.assertEqual(prop_updated.value, data['value'])
        self.assertEqual(prop_updated.name, prop.name)
        self.assertEqual(list(prop.product.all()), products[:1])

    def test_update_property_fail(self):
        prop = model_factories.PropertyFactory.create()
        data = {
            'name': '',  # "name" field is required
            'type': prop.type,
            'value': 'New value',
        }
        request = self.factory.put('', data)
        request.user = self.user
        response = PropertyViewSet.as_view({'put': 'update'})(request,
                                                              pk=prop.pk)
        self.assertEqual(response.status_code, 400)


class ProductCategoryRetrieveTest(ProductViewsBaseTest):

    def test_retrieve_product_category(self):
        product_category = model_factories.CategoryFactory(
            organization_uuid=self.organization_uuid
        )

        request = self.factory.get('')
        request.user = self.user
        request.session = self.session

        view = ProductCategoryViewSet.as_view({'get': 'retrieve'})
        response = view(request, pk=product_category.pk)

        self.assertEqual(response.status_code, 200)

    def test_retrieve_product_category_permission_failed(self):
        product_category = model_factories.CategoryFactory()

        request = self.factory.get('')
        request.user = self.user
        request.session = self.session

        view = ProductCategoryViewSet.as_view({'get': 'retrieve'})
        response = view(request, pk=product_category.pk)

        self.assertEqual(response.status_code, 403)

    def test_access_global_category(self):
        product_category = model_factories.CategoryFactory(is_global=True)

        request = self.factory.get('')
        request.user = self.user
        request.session = self.session

        view = ProductCategoryViewSet.as_view({'get': 'retrieve'})
        response = view(request, pk=product_category.pk)

        self.assertEqual(response.status_code, 200)


class ProductCategoryListTest(ProductViewsBaseTest):

    def test_list_org_categories(self):
        product_category_global = model_factories.CategoryFactory(is_global=True)
        product_category_org = model_factories.CategoryFactory(
            organization_uuid=self.organization_uuid,
        )

        self.assertEqual(Category.objects.count(), 2)

        request = self.factory.get('')
        request.user = self.user
        request.session = self.session

        view = ProductCategoryViewSet.as_view({'get': 'list'})
        response = view(request).render()
        content = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(content), 1)
        self.assertEqual(content[0]['uuid'], str(product_category_org.uuid))

    def test_list_filter_global_categories(self):
        product_category_global = model_factories.CategoryFactory(is_global=True)
        product_category_org = model_factories.CategoryFactory(
            organization_uuid=self.organization_uuid,
        )

        self.assertEqual(Category.objects.count(), 2)
        self.assertEqual(Category.objects.filter(is_global=True).count(), 1)

        request = self.factory.get('?is_global=true')
        request.user = self.user
        request.session = self.session

        view = ProductCategoryViewSet.as_view({'get': 'list'})
        response = view(request).render()
        content = json.loads(response.content)

        self.assertEqual(response.status_code, 200)
        self.assertEqual(len(content), 1)
        self.assertEqual(content[0]['uuid'], str(product_category_global.uuid))


class ProductCategoryCreateTest(ProductViewsBaseTest):

    def test_create_product_category(self):
        data = {
            'name': 'create-name',
        }

        request = self.factory.post('', data)
        request.user = self.user
        request.session = self.session

        view = ProductCategoryViewSet.as_view({'post': 'create'})
        response = view(request).render()

        self.assertEqual(response.status_code, 201)
        self.assertEqual(json.loads(response.content)['name'], 'create-name')


class ProductCategoryUpdateTest(ProductViewsBaseTest):

    def test_update_product_category(self):
        product_category = model_factories.CategoryFactory(
            organization_uuid=self.organization_uuid,
            name='old-name'
        )

        self.assertEqual(product_category.name, 'old-name')

        data = {
            'name': 'new-name',
        }

        request = self.factory.patch('', data)
        request.user = self.user
        request.session = self.session

        view = ProductCategoryViewSet.as_view({'patch': 'update'})
        response = view(request, pk=product_category.pk)

        self.assertEqual(response.status_code, 200)
        response.render()
        self.assertEqual(json.loads(response.content)['name'], 'new-name')


class ProductCategoryViewsDeleteTest(ProductViewsBaseTest):

    def test_delete_product_category(self):
        product_category = model_factories.CategoryFactory(
            organization_uuid=self.organization_uuid
        )
        self.assertEqual(Category.objects.count(), 1)

        request = self.factory.delete('')
        request.user = self.user
        request.session = self.session

        view = ProductCategoryViewSet.as_view({'delete': 'destroy'})
        response = view(request, pk=product_category.pk)

        self.assertEqual(response.status_code, 204)
        self.assertEqual(Category.objects.count(), 0)
