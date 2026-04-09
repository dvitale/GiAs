"""
PandasPianoRepository — thin facade sui metodi esistenti di DataRetriever.

Questo repository NON duplica logica: delega direttamente ai metodi statici
di `agents.data_agent.DataRetriever` e `BusinessLogic`, che già operano sul
DataFrame globale `piani_df` in memoria.

Scopo: mantenere al 100% la compatibilità con il comportamento pre-migrazione
quando la flag `data_source.repositories.piano` è impostata a `"pandas"`
(default). Il refactor di `piano_tools.py` chiama il repository, che a sua
volta chiama il codice legacy — zero breaking change.

Verrà rimosso in Fase 4 quando tutta la codebase sarà migrata a SQL.
"""

from typing import List, Dict, Any, Optional
import pandas as pd


class PandasPianoRepository:
    """Facade in-memory che delega a DataRetriever/BusinessLogic legacy."""

    def find_by_alias(self, piano_id: str) -> Optional[pd.DataFrame]:
        """Delega al metodo pandas legacy preservato in DataRetriever."""
        from agents.data_agent import DataRetriever
        # Chiama il metodo legacy per evitare ricorsione:
        # DataRetriever.get_piano_by_id delega a questo repository.
        method = getattr(
            DataRetriever,
            "_get_piano_by_id_pandas_legacy",
            DataRetriever.get_piano_by_id,
        )
        return method(piano_id)

    def search(
        self,
        query: str,
        sezione: Optional[str] = None,
        campionamento: Optional[bool] = None,
    ) -> List[Dict[str, Any]]:
        """Delega a DataRetriever.search_piani_by_db."""
        from agents.data_agent import DataRetriever
        # search_piani_by_db accetta None a runtime (firma legacy non Optional)
        kwargs: Dict[str, Any] = {"query": query}
        if sezione is not None:
            kwargs["sezione"] = sezione
        if campionamento is not None:
            kwargs["campionamento"] = campionamento
        return DataRetriever.search_piani_by_db(**kwargs)

    def count_attivita(self, piano_id: str) -> int:
        """Delega a BusinessLogic._count_attivita (helper per compare_plans_metrics)."""
        from agents.data_agent import BusinessLogic
        return BusinessLogic._count_attivita(piano_id)
