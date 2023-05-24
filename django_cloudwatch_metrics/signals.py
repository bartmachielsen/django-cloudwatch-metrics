"""Improved Python code for a Django OpenSearch DSL signal processor."""

import logging
from enum import Enum
from typing import List, Optional, Dict, Type, Union

from django.conf import settings
from django.db import models, transaction, connection
from django.db.models import Field, ManyToManyField
from django.dispatch import Signal
from django_opensearch_dsl import Document
from django_opensearch_dsl.registries import registry
from dataclasses import dataclass

logger = logging.getLogger(__name__)

class UpdateType(Enum):
    """Enum that represents the update type for document updates."""
    UPDATE = "UPDATE"
    DELETE = "DELETE"


@dataclass
class DocumentUpdate:
    """Data class to store document update information."""
    instance: models.Model
    document: Type[Document]
    pk: int
    update_type: UpdateType
    created: bool
    update_fields: Optional[List[str]]


class DocumentSignalProcessor:
    """Registry of models classes to a set of Document classes and handles signal processing."""

    def __init__(self):
        self.pending_updates: Dict[str, List[DocumentUpdate]] = {}
        self.setup()

    def commit_handler(self):
        """Commit handler for transactions, process pending updates."""
        logger.debug("Committing transaction")

        actions = self._prepare_actions()

        for document_class, document_actions in actions.items():
            document_class().bulk(document_actions, refresh=getattr(settings, "DJANGO_OPENSEARCH_DSL_SIGNALS_REFRESH", None))

        self.pending_updates.clear()

    def check_pending_updates_expired(self):
        """Check and clear expired pending updates."""
        if (
            not connection.run_on_commit and
            not connection.savepoint_ids
            and self.pending_updates
        ):
            logger.debug("Clearing pending updates")
            self.pending_updates.clear()

    def register_commit_handler(self):
        """Register commit handler for transactions."""
        if not any(
                f==self.commit_handler
                for (k, f, b) in connection.run_on_commit
        ):
            logger.debug(f"Registering on_commit handler")
            transaction.on_commit(self.commit_handler)

    def get_instance_document(self, instance: models.Model) -> Optional[Type[Document]]:
        """Get the document class for a given model instance."""
        return list((
                            registry._models.get(instance.__class__) or
                            registry._models.get(instance.__class__.__base__)
                    ) or [None])[0]

    def update_instance(self, instance: models.Model, update_fields: Optional[List[str]], created: bool, **kwargs):
        """Update the instance with the given fields and status."""
        document = self.get_instance_document(instance)

        if not document:
            return

        self.check_pending_updates_expired()

        update_fields = list(update_fields) if update_fields else None

        instance_key = f"{type(instance).__name__}:{instance.pk}"
        self.pending_updates[instance_key] = (
                self.pending_updates.get(instance_key, []) +
                [
                    DocumentUpdate(
                        instance=instance,
                        pk=instance.pk,
                        update_type=UpdateType.UPDATE,
                        document=document,
                        created=created,
                        update_fields=update_fields
                    )
                ]
        )
        self.register_commit_handler()

    def _get_related_many_fields(self, model: Type[models.Model], target_model: Type[models.Model]) -> List[Field]:
        """Get all related fields relevant."""
        fields: List[Field] = []
        for field in model._meta.get_fields():  # noqa
            if isinstance(field, ManyToManyField):
                if field.model == target_model:
                    fields.append(field)
        return fields

    def _get_related_fields(self, model: Type[models.Model], target_model: Type[models.Model]) -> List[Field]:
        """Get all related fields relevant."""
        fields: List[Field] = []
        for field in model._meta.get_fields():  # noqa
            if hasattr(field, "related_model"):
                if field.related_model == target_model:
                    fields.append(field)
        return fields

    def handle_save(self, sender: Type[models.Model], instance: models.Model, created: bool, update_fields: Optional[List[str]] = None, **kwargs):
        """Handle save signal for model instances."""
        self.update_instance(instance, update_fields, created, **kwargs)

        for doc in registry._get_related_doc(instance): # noqa
            # Loop all fields in instance, check if they are related to the document
            for field in self._get_related_fields(sender, doc.Django.model):  # noqa
                related_field_value = getattr(instance, field.name, None)

                if not related_field_value and hasattr(field, "get_accessor_name"):
                    related_field_value = getattr(instance, field.get_accessor_name(), None)

                if not related_field_value:
                    logger.warning(f"Failed to get related field value for {field} on {instance}")
                    continue

                if isinstance(related_field_value, models.Model):
                    self.update_instance(related_field_value, [field.remote_field.name], created, **kwargs)
                elif hasattr(related_field_value, "all"):
                    for related in related_field_value.all():
                        self.update_instance(related, [field.remote_field.name], created=False, **kwargs)

    def handle_delete(self, sender: Type[models.Model], instance: models.Model, **kwargs):
        """Handle delete signal for model instances."""
        if not instance.pk:
            return

        document = self.get_instance_document(instance)
        if not document:
            for doc in registry._get_related_doc(instance):  # noqa
                # Loop all fields in instance, check if they are related to the document
                for field in self._get_related_fields(sender, doc.Django.model):  # noqa
                    related_field_value = getattr(instance, field.name, None)

                    if not related_field_value and hasattr(field, "get_accessor_name"):
                        related_field_value = getattr(instance, field.get_accessor_name(), None)

                    if not related_field_value:
                        logger.warning(f"Failed to get related field value for {field} on {instance}")
                        continue

                    if isinstance(related_field_value, models.Model):
                        related_name = field._related_name # noqa
                        self.update_instance(related_field_value, update_fields=[related_name], created=False, **kwargs)
                    else:
                        if hasattr(field, "on_delete") and getattr(field, "on_delete") == models.CASCADE:
                            continue

                        if hasattr(related_field_value, "all"):
                            for related in related_field_value.all():
                                self.update_instance(related, update_fields=None, created=False, **kwargs)
            return

        self.check_pending_updates_expired()

        instance_key = f"{type(instance).__name__}:{instance.pk}"
        self.pending_updates[instance_key] = (
                self.pending_updates.get(instance_key, []) +
                [
                    DocumentUpdate(
                        instance=instance,
                        pk=instance.pk,
                        update_type=UpdateType.DELETE,
                        document=document,
                        created=False,
                        update_fields=None
                    )
                ]
        )

        self.register_commit_handler()

    def setup(self):
        """Setup signal connections."""
        models.signals.post_save.connect(self.handle_save)
        models.signals.pre_delete.connect(self.handle_delete)
        models.signals.m2m_changed.connect(self.handle_m2m_changed)

    def teardown(self):
        """Teardown signal connections."""
        models.signals.post_save.disconnect(self.handle_save)
        models.signals.pre_delete.disconnect(self.handle_delete)
        models.signals.m2m_changed.disconnect(self.handle_m2m_changed)

    def handle_m2m_changed(self, sender: Type[models.Model], instance: models.Model, action: str, **kwargs):
        """Handle many-to-many field change signals."""
        if action in ("post_add", "post_remove", "post_clear"):
            self.handle_save(sender, instance, created=False, **kwargs)

    def _prepare_actions(self) -> Dict[Type[Document], List[Dict]]:
        """Prepare actions for bulk indexing."""
        actions = {}

        for instance_key, historic_changes in self.pending_updates.items():
            document_class = historic_changes[0].document
            document_instance: Document = document_class()
            instance = historic_changes[-1].instance
            actions[document_class] = actions.get(document_class, [])

            if self._skip_update(historic_changes):
                logger.debug("Skipping update as object has been created and deleted in same session.")
                continue

            if self._check_delete(historic_changes):
                logger.debug(f"Deleting: {instance}")
                actions[document_class].append(self._prepare_delete_action(historic_changes))
                continue

            update_fields = self._get_update_fields(historic_changes)
            prepared_update = self._prepare_update(instance, document_instance, update_fields)

            if not prepared_update:
                logger.debug("No fields to update, skipping")
                continue

            actions[document_class].append(self._prepare_index_action(instance, document_instance, prepared_update))

        return actions

    @staticmethod
    def _skip_update(historic_changes: List[DocumentUpdate]) -> bool:
        """Check if update should be skipped."""
        return (
            # If the object has been created and deleted in the same session, skip
            (
                any(
                    change.update_type == UpdateType.DELETE
                    for change in historic_changes
                ) and
                any(
                    change.created
                    for change in historic_changes
                )
            ) or
            # No primary id, skip
            not historic_changes[-1].pk
        )

    @staticmethod
    def _check_delete(historic_changes: List[DocumentUpdate]) -> bool:
        """Check if a delete action should be performed."""
        return any(change.update_type == UpdateType.DELETE for change in historic_changes)

    @staticmethod
    def _get_update_fields(historic_changes: List[DocumentUpdate]) -> Union[str, List[str]]:
        """Get the update fields from historic changes."""
        if any(change.created for change in historic_changes):
            return "__all__"
        else:
            # Merge all update fields, make distinct as we only have to save them once
            update_fields: List[str] = []
            for change in historic_changes:
                if change.update_fields:
                    update_fields.extend(change.update_fields)
            return set(update_fields)


    @staticmethod
    def _prepare_update(instance: models.Model, document_instance: Document, update_fields: Union[str, List[str]]) -> Dict:
        """Prepare the update dictionary for the given instance."""
        return {name: prep_func(instance) for name, field, prep_func in document_instance._prepared_fields if
                update_fields=="__all__" or not update_fields or name in update_fields}

    @staticmethod
    def _prepare_delete_action(historic_changes: List[DocumentUpdate]) -> Dict:
        """Prepare a delete action for the given historic changes."""
        document_instance = historic_changes[0].document()
        return {
            "_op_type": "delete",
            "_index": document_instance._index._name,
            "_id": historic_changes[0].pk,
            "_source": None
        }

    @staticmethod
    def _prepare_index_action(instance: models.Model, document_instance: Document, prepared_update: Dict) -> Dict:
        """Prepare an index action for the given instance and update."""
        return {
            "_op_type": "index",
            "_index": document_instance._index._name,
            "_id": document_instance.generate_id(instance),
            "doc": prepared_update,
        }
